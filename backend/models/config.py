from typing import Any

from pydantic import BaseModel


class Config(BaseModel):
    """Configuration model."""

    model_parameters: dict[str, Any]
    system_prompt: str
    agent_config: dict[str, Any]
