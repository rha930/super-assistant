import json
import logging
import os
import re
import time
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

    def _wants_news(self, user_message: str) -> bool:
        text = (user_message or "").lower()
        keywords = [
            "news",
            "headline",
            "headlines",
            "latest",
            "recent",
            "breaking",
            "today",
            "this week",
            "current events",
            "what's happening",
            "whats happening",
            "what is happening",
            "what happened",
            "going on with",
            "update on",
            "updates on",
            "developments",
        ]
        return any(keyword in text for keyword in keywords)

    _NEWS_STOPWORDS = frozenset(
        {
            "the",
            "a",
            "an",
            "of",
            "on",
            "in",
            "for",
            "to",
            "about",
            "with",
            "and",
            "or",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "do",
            "does",
            "did",
            "you",
            "me",
            "my",
            "i",
            "we",
            "us",
            "please",
            "tell",
            "give",
            "show",
            "find",
            "get",
            "whats",
            "what",
            "whens",
            "when",
            "wheres",
            "where",
            "hows",
            "how",
            "any",
            "some",
            "latest",
            "recent",
            "news",
            "headline",
            "headlines",
            "today",
            "todays",
            "current",
            "breaking",
            "update",
            "updates",
            "happening",
            "happened",
            "going",
            "developments",
        }
    )

    def _build_news_query(self, user_message: str) -> str:
        """Strip conversational filler and trigger words so GNews gets clean keywords.

        Falls back to the original message when stripping leaves nothing.
        """
        original = (user_message or "").strip()
        tokens = re.findall(r"[a-z0-9]+", original.lower())
        keywords = [t for t in tokens if t not in self._NEWS_STOPWORDS and len(t) > 1]
        query = " ".join(keywords).strip()
        return query or original

    def _news_context_instructions(self) -> str:
        return (
            "You have access to a news search tool. Recent news articles relevant to the "
            "user's request are provided below as context. Ground your answer in these "
            "articles and cite the article titles and source names you use. If the articles "
            "do not answer the question, say so plainly."
        )

    def _format_news_articles(self, articles: list[dict[str, Any]]) -> str:
        lines = ["Recent news articles:"]
        for idx, article in enumerate(articles, start=1):
            title = str(article.get("title", "")).strip()
            source = str(article.get("source", "")).strip()
            published = str(article.get("published_at", "")).strip()
            description = str(article.get("description", "")).strip()
            url = str(article.get("url", "")).strip()
            lines.append(f"{idx}. {title} — {source} ({published})\n   {description}\n   {url}")
        return "\n".join(lines)

    def _maybe_fetch_news(
        self, user_message: str, gnews_service: Any | None
    ) -> tuple[str | None, dict[str, Any] | None]:
        """Fetch news articles if the message wants news and the tool is available.

        Returns (news_context, tool_call). Both are None when no search runs.
        """
        if gnews_service is None or not getattr(gnews_service, "is_available", lambda: False)():
            return None, None
        if not self._wants_news(user_message):
            return None, None

        query = self._build_news_query(user_message)
        start = time.monotonic()
        try:
            result = gnews_service.search(query)
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning("News search failed: %s", e)
            return None, {
                "name": "news_search",
                "status": "error",
                "duration": duration_ms,
                "inputs": {"query": query},
                "outputs": {"article_count": 0, "articles": []},
            }

        duration_ms = int((time.monotonic() - start) * 1000)
        articles = result.get("articles", []) or []
        news_context = self._format_news_articles(articles) if articles else None
        tool_call = {
            "name": "news_search",
            "status": "success",
            "duration": duration_ms,
            "inputs": {"query": query},
            "outputs": {
                "article_count": len(articles),
                "articles": [
                    {
                        "title": a.get("title", ""),
                        "source": a.get("source", ""),
                        "url": a.get("url", ""),
                        "published_at": a.get("published_at", ""),
                    }
                    for a in articles
                ],
            },
        }
        return news_context, tool_call

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
        news_context: str | None = None,
    ) -> str:
        sections = []

        if system_prompt:
            sections.append(f"System: {system_prompt}")

        if self._wants_visualization(user_message):
            sections.append(f"System: {self._graph_output_instructions()}")

        if news_context:
            sections.append(f"System: {self._news_context_instructions()}")
            sections.append(f"Context: {news_context}")

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

            news_context, news_tool_call = self._maybe_fetch_news(user_message, kwargs.get("gnews_service"))

            prompt = self._build_prompt(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                max_messages=kwargs.get("context_max_messages", 12),
                max_input_chars=kwargs.get("context_max_input_chars", 12000),
                news_context=news_context,
            )

            tool_calls = [news_tool_call] if news_tool_call else []

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
                    yield {"chunk": chunk, "done": False, "metadata": {"model": model, "tool_calls": tool_calls}}

                if done:
                    yield {
                        "chunk": "",
                        "done": True,
                        "metadata": {
                            "tokens_used": data.get("eval_count", 0),
                            "tool_calls": tool_calls,
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
