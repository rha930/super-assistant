"""Tests for provider selection (Ollama or Gemini)."""

import pytest
from services.chat_service import ChatService
from services.config_service import ConfigService
from services.gemini_service import GeminiService

# ---------------------------------------------------------------------------
# GeminiService
# ---------------------------------------------------------------------------

GEMINI_CONFIG = {
    "enabled": True,
    "model": "gemini-1.5-flash",
    "base_url": "https://example.test/v1beta",
    "timeout_seconds": 30,
    "max_output_tokens": 512,
    "models": ["gemini-1.5-flash", "gemini-1.5-pro"],
}


class TestGeminiServiceAvailability:
    def test_unavailable_without_key(self):
        svc = GeminiService(GEMINI_CONFIG, api_key="")
        assert svc.is_available() is False
        assert svc.available_models() == []

    def test_unavailable_when_disabled(self):
        cfg = {**GEMINI_CONFIG, "enabled": False}
        svc = GeminiService(cfg, api_key="key")
        assert svc.is_available() is False

    def test_available_with_key_and_enabled(self):
        svc = GeminiService(GEMINI_CONFIG, api_key="key")
        assert svc.is_available() is True
        assert svc.available_models() == ["gemini-1.5-flash", "gemini-1.5-pro"]


class TestGeminiServiceGenerate:
    def test_generate_raises_when_unavailable(self):
        svc = GeminiService(GEMINI_CONFIG, api_key="")
        with pytest.raises(RuntimeError):
            svc.generate("hello")

    def test_generate_parses_response(self, monkeypatch):
        svc = GeminiService(GEMINI_CONFIG, api_key="key")

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "candidates": [{"content": {"parts": [{"text": "Hello "}, {"text": "world"}]}}],
                    "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2},
                }

        captured = {}

        def fake_post(url, params=None, json=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            captured["json"] = json
            return FakeResponse()

        monkeypatch.setattr("services.gemini_service.requests.post", fake_post)

        result = svc.generate("hi", system_prompt="be nice")

        assert result["content"] == "Hello world"
        assert result["provider"] == "gemini"
        assert result["model"] == "gemini-1.5-flash"
        assert result["usage"] == {"input_tokens": 5, "output_tokens": 2}
        # API key passed as query param, not in the URL.
        assert captured["params"] == {"key": "key"}
        assert "key" not in captured["url"]

    def test_generate_wraps_network_error(self, monkeypatch):
        import requests

        svc = GeminiService(GEMINI_CONFIG, api_key="key")

        def fake_post(*args, **kwargs):
            raise requests.exceptions.ConnectionError("boom")

        monkeypatch.setattr("services.gemini_service.requests.post", fake_post)

        with pytest.raises(RuntimeError):
            svc.generate("hi")

    def test_generate_surfaces_http_status_and_message(self, monkeypatch):
        import requests

        svc = GeminiService(GEMINI_CONFIG, api_key="key")

        class FakeErrorResponse:
            status_code = 404
            text = '{"error": {"message": "models/x is not found"}}'

            def json(self):
                return {"error": {"message": "models/x is not found"}}

            def raise_for_status(self):
                raise requests.exceptions.HTTPError(response=self)

        monkeypatch.setattr(
            "services.gemini_service.requests.post",
            lambda *a, **k: FakeErrorResponse(),
        )

        with pytest.raises(RuntimeError) as exc_info:
            svc.generate("hi")

        message = str(exc_info.value)
        assert "404" in message
        assert "models/x is not found" in message
        assert "key" not in message


# ---------------------------------------------------------------------------
# ConfigService provider validation
# ---------------------------------------------------------------------------


class TestConfigServiceProvider:
    def test_default_provider_is_ollama(self):
        svc = ConfigService()
        assert svc.get_config()["provider"] == "ollama"

    def test_accepts_ollama(self):
        svc = ConfigService()
        updated = svc.update_config({"provider": "ollama"})
        assert updated["provider"] == "ollama"

    def test_rejects_invalid_provider(self):
        svc = ConfigService()
        with pytest.raises(ValueError):
            svc.update_config({"provider": "openai"})

    def test_rejects_gemini_when_unavailable(self, monkeypatch):
        svc = ConfigService()
        monkeypatch.setattr(svc, "_gemini_available", lambda: False)
        with pytest.raises(ValueError):
            svc.update_config({"provider": "gemini"})

    def test_accepts_gemini_when_available(self, monkeypatch):
        svc = ConfigService()
        monkeypatch.setattr(svc, "_gemini_available", lambda: True)
        updated = svc.update_config({"provider": "gemini"})
        assert updated["provider"] == "gemini"


# ---------------------------------------------------------------------------
# ChatService provider routing
# ---------------------------------------------------------------------------


class _FakeHistoryRepo:
    def __init__(self):
        self.messages = []

    def append_message(self, **kwargs):
        self.messages.append(kwargs)

    def get_messages(self, user_id, conversation_id, limit=None):
        return []

    def list_conversations(self, user_id, limit=50):
        return []


class _FakeGemini:
    def __init__(self, available=True, fail=False):
        self._available = available
        self._fail = fail

    def is_available(self):
        return self._available

    def generate(self, **kwargs):
        if self._fail:
            raise RuntimeError("gemini down")
        return {
            "content": "from gemini",
            "model": "gemini-1.5-flash",
            "provider": "gemini",
            "usage": {"input_tokens": 1, "output_tokens": 2},
        }


def _make_chat_service(monkeypatch, provider, gemini):
    svc = ChatService()
    svc.history_repo = _FakeHistoryRepo()
    # Fixed config for the request.
    cfg = {
        "provider": provider,
        "model": "llama3",
        "model_parameters": {"temperature": 0.7, "top_p": 0.9, "max_tokens": 100},
        "system_prompt": "sys",
        "context_config": {"max_messages": 12, "max_input_chars": 12000},
        "gemini": {"model": "gemini-1.5-flash"},
    }
    monkeypatch.setattr(svc, "_refresh_config", lambda: svc.__dict__.update(config=cfg) or cfg)
    svc.config = cfg
    monkeypatch.setattr(svc, "_build_gemini_service", lambda: gemini)
    # Stub Ollama agent.
    monkeypatch.setattr(
        svc.agent, "invoke_agent", lambda **kwargs: {"response": "from ollama", "metadata": {"tool_calls": []}}
    )
    monkeypatch.setattr(svc.agent, "_wants_visualization", lambda msg: False)
    return svc


class TestChatServiceRouting:
    def test_routes_to_ollama(self, monkeypatch):
        svc = _make_chat_service(monkeypatch, "ollama", _FakeGemini(available=True))
        result = svc.process_message("hi", conversation_id="c1", user_id="u1")
        assert result["response"] == "from ollama"
        assert result["metadata"]["provider"] == "ollama"

    def test_routes_to_gemini(self, monkeypatch):
        svc = _make_chat_service(monkeypatch, "gemini", _FakeGemini(available=True))
        result = svc.process_message("hi", conversation_id="c1", user_id="u1")
        assert result["response"] == "from gemini"
        assert result["metadata"]["provider"] == "gemini"

    def test_gemini_failure_falls_back_to_ollama(self, monkeypatch):
        svc = _make_chat_service(monkeypatch, "gemini", _FakeGemini(available=True, fail=True))
        result = svc.process_message("hi", conversation_id="c1", user_id="u1")
        assert result["response"] == "from ollama"
        assert result["metadata"]["provider"] == "ollama"
        assert result["metadata"]["fallback_from"] == "gemini"

    def test_gemini_selected_but_unavailable_uses_ollama(self, monkeypatch):
        svc = _make_chat_service(monkeypatch, "gemini", _FakeGemini(available=False))
        result = svc.process_message("hi", conversation_id="c1", user_id="u1")
        assert result["response"] == "from ollama"
        assert result["metadata"]["provider"] == "ollama"
