from pydantic import BaseModel
from typing import Dict, Any

class Config(BaseModel):
    """Configuration model."""
    model_parameters: Dict[str, Any]
    system_prompt: str
    agent_config: Dict[str, Any]
