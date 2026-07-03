import json
import logging
import os
from collections.abc import Generator
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Import with fallback defaults
try:
    from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
except ImportError:
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")
    OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))


class StrandsAgentService:
    """Service for interacting with a localhosted Ollama model."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        """
        Initialize the local Ollama service client.

        Args:
            base_url: Ollama server base URL (defaults to OLLAMA_BASE_URL env or config)
            model: Default model name (defaults to OLLAMA_MODEL env or config)
        """
        self.base_url = (base_url or OLLAMA_BASE_URL or "http://localhost:11434").rstrip("/")
        self.model = model or OLLAMA_MODEL or "gemma4"
        logger.info("Ollama service initialized at %s with model %s", self.base_url, self.model)

    def _wants_visualization(self, user_message: str) -> bool:
        text = (user_message or "").lower()
        keywords = [
            "plot",
            "chart",
            "graph",
            "visualize",
            "visualise",
            "trend",
            "compare",
            "comparison",
            "distribution",
            "histogram",
            "line chart",
            "bar chart",
            "pie chart",
        ]
        return any(keyword in text for keyword in keywords)

    def _graph_output_instructions(self) -> str:
        return (
            "When the user asks for a chart/graph/visualization and data is available, "
            "you MUST include one JSON graph artifact in a fenced ```json block using this exact schema:\n"
            "{\n"
            '  "type": "graph",\n'
            '  "graph": {\n'
            '    "id": "graph_unique_id",\n'
            '    "title": "Descriptive title",\n'
            '    "chartType": "line" | "bar" | "pie",\n'
            '    "xLabel": "Category",\n'
            '    "yLabel": "Value",\n'
            '    "series": [\n'
            "      {\n"
            '        "name": "Series 1",\n'
            '        "data": [\n'
            '          {"x": "Label 1", "y": 10},\n'
            '          {"x": "Label 2", "y": 20}\n'
            "        ]\n"
            "      }\n"
            "    ],\n"
            '    "options": {"showLegend": true, "stacked": false}\n'
            "  }\n"
            "}\n"
            "Rules: only use chartType line/bar/pie; y must be numeric; include at least 2 data points; "
            "keep JSON valid and do not include comments. Also include a short plain-language summary outside the JSON block."
        )

    def _build_prompt(
        self,
        user_message: str,
        system_prompt: str | None = None,
        conversation_history: list | None = None,
        max_messages: int = 12,
        max_input_chars: int = 12000,
    ) -> str:
        sections = []

        if system_prompt:
            sections.append(f"System: {system_prompt}")

        if self._wants_visualization(user_message):
            sections.append(f"System: {self._graph_output_instructions()}")

        history = conversation_history or []
        if max_messages > 0 and history:
            history = history[-max_messages:]

        for item in history:
            role = str(item.get("role", "")).strip().lower()
            content = str(item.get("content", "")).strip()
            if not content:
                continue

            if role == "user":
                sections.append(f"User: {content}")
            elif role in ("assistant", "agent"):
                sections.append(f"Assistant: {content}")
            else:
                sections.append(f"Context: {content}")

        sections.append(f"User: {user_message}")
        sections.append("Assistant:")

        prompt = "\n\n".join(sections)
        if len(prompt) > max_input_chars:
            prompt = prompt[-max_input_chars:]

        return prompt

    def stream_agent(
        self, user_message: str, system_prompt: str | None = None, conversation_history: list | None = None, **kwargs
    ) -> Generator[dict[str, Any], None, None]:
        """Stream response chunks from Ollama /api/generate."""
        try:
            model = kwargs.get("model", self.model)
            prompt = self._build_prompt(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                max_messages=kwargs.get("context_max_messages", 12),
                max_input_chars=kwargs.get("context_max_input_chars", 12000),
            )

            options = {
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "num_predict": kwargs.get("max_tokens", 1000),
            }

            payload = {"model": model, "prompt": prompt, "stream": True, "options": options}

            response = requests.post(
                f"{self.base_url}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT_SECONDS, stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                data = json.loads(line)
                chunk = data.get("response", "")
                done = bool(data.get("done", False))

                if chunk:
                    yield {"chunk": chunk, "done": False, "metadata": {"model": model, "tool_calls": []}}

                if done:
                    yield {
                        "chunk": "",
                        "done": True,
                        "metadata": {
                            "tokens_used": data.get("eval_count", 0),
                            "tool_calls": [],
                            "model": model,
                            "total_duration_ns": data.get("total_duration", 0),
                        },
                    }
                    break

        except requests.exceptions.ConnectionError as e:
            msg = f"Failed to connect to Ollama at {self.base_url}. Make sure Ollama is running: {str(e)}"
            logger.error(msg)
            raise RuntimeError(msg) from e
        except requests.exceptions.Timeout as e:
            msg = f"Ollama request timed out after {OLLAMA_TIMEOUT_SECONDS}s at {self.base_url}"
            logger.error(msg)
            raise RuntimeError(msg) from e
        except Exception as e:
            logger.error("Error invoking Ollama model at %s: %s", self.base_url, e)
            raise

    def invoke_agent(
        self,
        agent_id: str | None,
        session_id: str | None,
        user_message: str,
        system_prompt: str | None = None,
        conversation_history: list | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Invoke the Strands agent with a user message.

        Args:
            agent_id: Unused placeholder for compatibility
            session_id: Unused placeholder for compatibility
            user_message: User input message
            system_prompt: Optional system prompt override
            **kwargs: Additional generation parameters (temperature, top_p, max_tokens, model)

        Returns:
            Agent response and metadata
        """
        full_text = ""
        metadata: dict[str, Any] = {"tool_calls": []}

        for event in self.stream_agent(
            user_message=user_message, system_prompt=system_prompt, conversation_history=conversation_history, **kwargs
        ):
            if event.get("chunk"):
                full_text += event["chunk"]
            if event.get("done"):
                metadata = event.get("metadata", metadata)

        return {"response": full_text, "metadata": metadata}
