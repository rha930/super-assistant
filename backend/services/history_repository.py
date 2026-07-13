from typing import Any, Protocol


class ChatHistoryRepository(Protocol):
    def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    def get_messages(self, user_id: str, conversation_id: str, limit: int | None = None) -> list[dict[str, Any]]: ...

    def delete_conversation(self, user_id: str, conversation_id: str) -> None: ...

    def delete_all_for_user(self, user_id: str) -> None: ...

    def list_conversations(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]: ...
