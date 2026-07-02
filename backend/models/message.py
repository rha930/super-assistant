from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Message model."""
    role: str  # 'user' or 'agent'
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
