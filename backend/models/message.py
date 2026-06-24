from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any, Optional, List

class Message(BaseModel):
    """Message model."""
    role: str  # 'user' or 'agent'
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }
