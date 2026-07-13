import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class NoteRepository:
    """Local SQLite-backed repository for user-scoped notes."""

    def __init__(self, db_path: str = './backend/data/chat_history.db'):
        self.db_path = db_path
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
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT 'Untitled Note',
                    content TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notes_user_updated
                ON notes (user_id, updated_at DESC)
                """
            )
            conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "content": row["content"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def create_note(
        self,
        user_id: str,
        title: str = "Untitled Note",
        content: str = "",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        note_id = f"note_{uuid.uuid4().hex}"
        title = (title or "Untitled Note").strip()[:200]
        content = (content or "")[:100_000]

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notes (id, user_id, title, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (note_id, user_id, title, content, now, now),
            )
            conn.commit()

        return {
            "id": note_id,
            "user_id": user_id,
            "title": title,
            "content": content,
            "created_at": now,
            "updated_at": now,
        }

    def get_note(self, user_id: str, note_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE id = ? AND user_id = ?",
                (note_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def update_note(
        self,
        user_id: str,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> dict[str, Any] | None:
        existing = self.get_note(user_id, note_id)
        if existing is None:
            return None

        now = datetime.now(timezone.utc).isoformat()
        new_title = existing["title"] if title is None else (title or "Untitled Note").strip()[:200]
        new_content = existing["content"] if content is None else (content or "")[:100_000]

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE notes SET title = ?, content = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (new_title, new_content, now, note_id, user_id),
            )
            conn.commit()

        existing["title"] = new_title
        existing["content"] = new_content
        existing["updated_at"] = now
        return existing

    def append_content(self, user_id: str, note_id: str, content: str) -> dict[str, Any] | None:
        existing = self.get_note(user_id, note_id)
        if existing is None:
            return None

        current = existing["content"]
        addition = (content or "")[:100_000]
        new_content = f"{current}\n\n{addition}" if current else addition
        new_content = new_content[:100_000]

        return self.update_note(user_id, note_id, content=new_content)

    def delete_note(self, user_id: str, note_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM notes WHERE id = ? AND user_id = ?",
                (note_id, user_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def list_notes(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, title, SUBSTR(content, 1, 120) AS content,
                       created_at, updated_at
                FROM notes
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "preview": (row["content"] or "")[:120],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
