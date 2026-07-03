import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class LocalChatHistoryRepository:
    """Local SQLite-backed repository for user-scoped chat history."""

    def __init__(self, db_path: str, max_messages_per_conversation: int = 200):
        self.db_path = db_path
        self.max_messages_per_conversation = max_messages_per_conversation
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_user_conversation_time
                ON chat_messages(user_id, conversation_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_user_time
                ON chat_messages(user_id, timestamp)
                """
            )
            conn.commit()

    def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        message_id = f"msg_{uuid.uuid4().hex}"
        message = {
            "id": message_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "metadata": metadata or {},
        }

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (id, user_id, conversation_id, role, content, timestamp, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message["id"],
                    message["user_id"],
                    message["conversation_id"],
                    message["role"],
                    message["content"],
                    message["timestamp"],
                    json.dumps(message["metadata"]),
                ),
            )

            # Keep only the latest N messages for the conversation.
            conn.execute(
                """
                DELETE FROM chat_messages
                WHERE id IN (
                    SELECT id
                    FROM chat_messages
                    WHERE user_id = ? AND conversation_id = ?
                    ORDER BY timestamp DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (user_id, conversation_id, self.max_messages_per_conversation),
            )
            conn.commit()

        return message

    def get_messages(self, user_id: str, conversation_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        query = (
            "SELECT id, user_id, conversation_id, role, content, timestamp, metadata_json "
            "FROM chat_messages WHERE user_id = ? AND conversation_id = ? ORDER BY timestamp ASC"
        )
        params: list[Any] = [user_id, conversation_id]
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        messages: list[dict[str, Any]] = []
        for row in rows:
            metadata: dict[str, Any] = {}
            raw_meta = row["metadata_json"]
            if raw_meta:
                try:
                    metadata = json.loads(raw_meta)
                except json.JSONDecodeError:
                    logger.warning("Invalid metadata_json for message_id=%s", row["id"])

            messages.append(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "conversation_id": row["conversation_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"],
                    "metadata": metadata,
                }
            )
        return messages

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM chat_messages WHERE user_id = ? AND conversation_id = ?",
                (user_id, conversation_id),
            )
            conn.commit()

    def delete_all_for_user(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
            conn.commit()

    def list_conversations(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    conversation_id,
                    MIN(timestamp) AS first_message_at,
                    MAX(timestamp) AS last_message_at,
                    COUNT(*) AS message_count,
                    SUBSTR(
                        COALESCE(
                            (
                                SELECT content
                                FROM chat_messages m2
                                WHERE m2.user_id = m.user_id
                                  AND m2.conversation_id = m.conversation_id
                                  AND m2.role = 'user'
                                ORDER BY m2.timestamp ASC
                                LIMIT 1
                            ),
                            (
                                SELECT content
                                FROM chat_messages m3
                                WHERE m3.user_id = m.user_id
                                  AND m3.conversation_id = m.conversation_id
                                ORDER BY m3.timestamp ASC
                                LIMIT 1
                            ),
                            ''
                        ),
                        1,
                        120
                    ) AS preview
                FROM chat_messages m
                WHERE user_id = ?
                GROUP BY conversation_id
                ORDER BY last_message_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [
            {
                "conversation_id": row["conversation_id"],
                "first_message_at": row["first_message_at"],
                "last_message_at": row["last_message_at"],
                "message_count": row["message_count"],
                "preview": row["preview"] or "",
            }
            for row in rows
        ]
