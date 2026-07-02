import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis

logger = logging.getLogger(__name__)


class RedisChatHistoryRepository:
    """Redis-backed repository for user-scoped chat history."""

    def __init__(
        self,
        redis_url: str,
        redis_prefix: str = 'chat',
        max_messages_per_conversation: int = 200,
    ):
        self.redis_prefix = redis_prefix
        self.max_messages_per_conversation = max_messages_per_conversation
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def _messages_key(self, user_id: str, conversation_id: str) -> str:
        return f"{self.redis_prefix}:{user_id}:{conversation_id}:messages"

    def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        message = {
            'id': f"msg_{uuid.uuid4().hex}",
            'user_id': user_id,
            'conversation_id': conversation_id,
            'role': role,
            'content': content,
            'timestamp': timestamp,
            'metadata': metadata or {},
        }

        key = self._messages_key(user_id, conversation_id)
        score = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.client.zadd(key, {json.dumps(message): score})

        # Keep only the latest N records.
        over_count = self.client.zcard(key) - self.max_messages_per_conversation
        if over_count > 0:
            self.client.zremrangebyrank(key, 0, over_count - 1)

        return message

    def get_messages(self, user_id: str, conversation_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        key = self._messages_key(user_id, conversation_id)
        raw_items = self.client.zrange(key, 0, -1)
        if limit is not None and limit > 0:
            raw_items = raw_items[-limit:]

        messages: list[dict[str, Any]] = []
        for item in raw_items:
            try:
                messages.append(json.loads(item))
            except json.JSONDecodeError:
                logger.warning('Failed to decode redis chat message item')
        return messages

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        self.client.delete(self._messages_key(user_id, conversation_id))

    def delete_all_for_user(self, user_id: str) -> None:
        pattern = f"{self.redis_prefix}:{user_id}:*:messages"
        keys = list(self.client.scan_iter(match=pattern))
        if keys:
            self.client.delete(*keys)

    def list_conversations(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        pattern = f"{self.redis_prefix}:{user_id}:*:messages"
        results: list[dict[str, Any]] = []

        for key in self.client.scan_iter(match=pattern):
            key_str = str(key)
            # Expected format: prefix:user_id:conversation_id:messages
            parts = key_str.split(':')
            if len(parts) < 4:
                continue
            conversation_id = parts[-2]

            raw_messages = self.client.zrange(key_str, 0, -1)
            if not raw_messages:
                continue

            parsed = []
            for item in raw_messages:
                try:
                    parsed.append(json.loads(item))
                except json.JSONDecodeError:
                    continue

            if not parsed:
                continue

            first_ts = parsed[0].get('timestamp')
            last_ts = parsed[-1].get('timestamp')
            preview = ''
            for msg in parsed:
                if msg.get('role') == 'user' and msg.get('content'):
                    preview = str(msg.get('content'))[:120]
                    break
            if not preview:
                preview = str(parsed[0].get('content') or '')[:120]

            results.append(
                {
                    'conversation_id': conversation_id,
                    'first_message_at': first_ts,
                    'last_message_at': last_ts,
                    'message_count': len(parsed),
                    'preview': preview,
                }
            )

        results.sort(key=lambda x: x.get('last_message_at') or '', reverse=True)
        return results[:limit]
