from typing import Any, Dict, List, Optional, Protocol


class ChatHistoryRepository(Protocol):
    def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ...

    def get_messages(self, user_id: str, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        ...

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        ...

    def delete_all_for_user(self, user_id: str) -> None:
        ...

    def list_conversations(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        ...
