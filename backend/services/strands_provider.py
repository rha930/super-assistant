"""Factory for building a configured strands.Agent.

Provides a single entry point — build_agent() — that selects the right
model provider (Ollama or Gemini) based on the current app config and
constructs an Agent pre-loaded with conversation history and tools.
"""

import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


def _history_to_strands_messages(history: list) -> list:
    """Convert the app's flat history format to Strands SDK message format.

    App format:  {"role": "user"|"agent", "content": "..."}
    Strands format: {"role": "user"|"assistant", "content": [{"text": "..."}]}
    """
    messages = []
    for item in history:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        strands_role = "user" if role == "user" else "assistant"
        messages.append({"role": strands_role, "content": [{"text": content}]})
    return messages


def build_agent(
    provider: str,
    config: dict[str, Any],
    tools: list,
    history: list,
    callback_handler: Callable | None,
    *,
    gemini_api_key: str = "",
    widget_context_block: str | None = None,
):
    """Build a strands.Agent for the given provider.

    Args:
        provider: "ollama" or "gemini".
        config: Current app config dict (model, system_prompt, model_parameters…).
        tools: Pre-built @tool callables to register with the agent.
        history: App-format conversation history to pre-load.
        callback_handler: Event callback (None → no output; pass a callable
            to receive streaming events).
        gemini_api_key: Gemini API key — only used when provider=="gemini".
        widget_context_block: Natural-language description of the user's active
            widget state, appended to the system prompt when present.
    """
    from strands import Agent
    from strands.agent.conversation_manager import SlidingWindowConversationManager

    model = _build_model(provider, config, gemini_api_key)
    system_prompt = config.get("system_prompt") or "You are a helpful AI assistant."
    if widget_context_block:
        system_prompt = f"{system_prompt}\n\n{widget_context_block}"
    messages = _history_to_strands_messages(history)

    return Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        messages=messages,
        callback_handler=callback_handler,
        # One agent per request — disable SDK-level conversation management
        # so history is handled exclusively by the app's history_repo.
        conversation_manager=SlidingWindowConversationManager(),
    )


def _build_model(provider: str, config: dict[str, Any], gemini_api_key: str):
    params = config.get("model_parameters", {})
    model_id = config.get("model")

    if provider == "gemini" and gemini_api_key:
        from strands.models.gemini import GeminiModel

        logger.info("Building GeminiModel (model=%s)", model_id)
        return GeminiModel(
            client_args={"api_key": gemini_api_key},
            model_id=model_id or "gemini-2.5-flash",
            params={
                "temperature": float(params.get("temperature", 0.7)),
                "max_output_tokens": int(params.get("max_tokens", 1000)),
            },
        )

    if provider == "gemini":
        logger.warning("provider=gemini but no API key configured; falling back to Ollama")

    from strands.models.ollama import OllamaModel

    try:
        from config import OLLAMA_BASE_URL
    except ImportError:
        OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    logger.info("Building OllamaModel (host=%s, model=%s)", OLLAMA_BASE_URL, model_id)
    return OllamaModel(
        host=OLLAMA_BASE_URL or "http://localhost:11434",
        model_id=model_id or "gemma4",
    )
