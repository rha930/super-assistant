import logging
from collections.abc import Generator
from typing import Any

import requests

logger = logging.getLogger(__name__)


class GeminiService:
    """Client for the Google Gemini API.

    Provides chat-style generation compatible with the agent flow so the
    ChatService can route generation to Gemini when it is the selected provider.
    The API key is supplied from the environment and is never logged or returned.
    """

    def __init__(self, config: dict[str, Any] | None = None, api_key: str = ''):
        config = config or {}
        self.enabled = bool(config.get('enabled', False))
        self.api_key = api_key or ''
        self.model = config.get('model', 'gemini-1.5-flash')
        self.base_url = str(config.get('base_url', 'https://generativelanguage.googleapis.com/v1beta')).rstrip('/')
        self.timeout_seconds = int(config.get('timeout_seconds', 60))
        self.max_output_tokens = int(config.get('max_output_tokens', 2048))
        self.models: list[str] = list(config.get('models', []) or [])
        logger.info(
            "Gemini service initialized (enabled=%s, model=%s, models=%s)",
            self.enabled, self.model, self.models,
        )

    def is_available(self) -> bool:
        """Return True when Gemini is enabled and an API key is configured."""
        return bool(self.enabled and self.api_key)

    def available_models(self) -> list[str]:
        """Return the allow-list of selectable Gemini models (empty if disabled)."""
        if not self.is_available():
            return []
        return list(self.models)

    def _build_contents(
        self,
        user_message: str,
        conversation_history: list | None = None,
    ) -> list[dict[str, Any]]:
        """Map conversation history + the new message to Gemini `contents`."""
        contents: list[dict[str, Any]] = []
        for item in conversation_history or []:
            role = str(item.get('role', '')).strip().lower()
            text = str(item.get('content', '')).strip()
            if not text:
                continue
            gemini_role = 'user' if role == 'user' else 'model'
            contents.append({'role': gemini_role, 'parts': [{'text': text}]})

        contents.append({'role': 'user', 'parts': [{'text': user_message}]})
        return contents

    def generate(
        self,
        user_message: str,
        system_prompt: str | None = None,
        conversation_history: list | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Call the Gemini generateContent endpoint and return the full result.

        Returns: { 'content': str, 'model': str, 'provider': 'gemini',
                   'usage': {...} | None }
        Raises RuntimeError on any API/network failure so callers can fall back.
        """
        if not self.is_available():
            raise RuntimeError('Gemini is not available (disabled or missing API key)')

        model = kwargs.get('model') or self.model
        url = f"{self.base_url}/models/{model}:generateContent"

        payload: dict[str, Any] = {
            'contents': self._build_contents(user_message, conversation_history),
            'generationConfig': {
                'temperature': kwargs.get('temperature', 0.7),
                'topP': kwargs.get('top_p', 0.9),
                'maxOutputTokens': kwargs.get('max_tokens', self.max_output_tokens),
            },
        }
        if system_prompt:
            payload['systemInstruction'] = {'parts': [{'text': system_prompt}]}

        logger.info("Calling Gemini generateContent (model=%s)", model)
        try:
            response = requests.post(
                url,
                params={'key': self.api_key},
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout as e:
            logger.error("Gemini request timed out after %ss (model=%s)", self.timeout_seconds, model)
            raise RuntimeError(f"Gemini request timed out after {self.timeout_seconds}s") from e
        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, 'status_code', 'unknown')
            api_message = self._extract_error_message(e.response)
            # Log full detail server-side (status + API message) to aid debugging.
            logger.error("Gemini API error %s (model=%s): %s", status, model, api_message)
            raise RuntimeError(f"Gemini API error {status}: {api_message}") from e
        except requests.exceptions.RequestException as e:
            # Never include the API key in error output.
            logger.error("Gemini request failed (model=%s): %s", model, e.__class__.__name__)
            raise RuntimeError(f"Gemini request failed: {e.__class__.__name__}") from e
        except ValueError as e:
            logger.error("Gemini returned a malformed response (model=%s)", model)
            raise RuntimeError('Gemini returned a malformed response') from e

        content = self._extract_text(data)
        usage = self._extract_usage(data)
        logger.info(
            "Gemini call succeeded (model=%s, output_tokens=%s)",
            model, (usage or {}).get('output_tokens', 0),
        )

        return {
            'content': content,
            'model': model,
            'provider': 'gemini',
            'usage': usage,
        }

    def stream_generate(
        self,
        user_message: str,
        system_prompt: str | None = None,
        conversation_history: list | None = None,
        **kwargs,
    ) -> Generator[dict[str, Any], None, None]:
        """Yield chunk events compatible with StrandsAgentService.stream_agent.

        Phase 1 performs a single non-streamed request and emits the full text
        as one content chunk followed by a terminal done event.
        """
        result = self.generate(
            user_message=user_message,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            **kwargs,
        )
        model = result.get('model', self.model)
        content = result.get('content', '')

        if content:
            yield {
                'chunk': content,
                'done': False,
                'metadata': {
                    'provider': 'gemini',
                    'model': model,
                    'tool_calls': [],
                },
            }

        usage = result.get('usage') or {}
        yield {
            'chunk': '',
            'done': True,
            'metadata': {
                'provider': 'gemini',
                'model': model,
                'tool_calls': [],
                'tokens_used': usage.get('output_tokens', 0),
            },
        }

    @staticmethod
    def _extract_error_message(response) -> str:
        """Best-effort extraction of the Gemini API error message.

        Parses the JSON error body (`error.message`) when present; falls back to
        a truncated text body. Never includes the API key (it is only sent as a
        query param, not echoed in error bodies).
        """
        if response is None:
            return 'no response body'
        try:
            body = response.json()
            message = (body.get('error') or {}).get('message')
            if message:
                return str(message)
        except (ValueError, AttributeError):
            pass
        text = getattr(response, 'text', '') or ''
        return text[:200] if text else 'unknown error'

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        candidates = data.get('candidates') or []
        if not candidates:
            return ''
        parts = (candidates[0].get('content') or {}).get('parts') or []
        return ''.join(part.get('text', '') for part in parts).strip()

    @staticmethod
    def _extract_usage(data: dict[str, Any]) -> dict[str, int] | None:
        meta = data.get('usageMetadata')
        if not meta:
            return None
        return {
            'input_tokens': int(meta.get('promptTokenCount', 0)),
            'output_tokens': int(meta.get('candidatesTokenCount', 0)),
        }
