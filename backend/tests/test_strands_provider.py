"""Unit tests for strands_provider.build_agent()."""




class TestBuildAgent:
    """Tests for build_agent() provider selection and fallback."""

    def _minimal_config(self, model="llama3"):
        return {
            "model": model,
            "system_prompt": "You are helpful.",
            "model_parameters": {"temperature": 0.7, "max_tokens": 512},
        }

    def test_ollama_provider_builds_ollama_model(self):
        from services.strands_provider import build_agent
        from strands.models.ollama import OllamaModel

        agent = build_agent(
            provider="ollama",
            config=self._minimal_config(),
            tools=[],
            history=[],
            callback_handler=None,
        )

        assert isinstance(agent.model, OllamaModel)

    def test_gemini_provider_builds_gemini_model(self):
        from services.strands_provider import build_agent
        from strands.models.gemini import GeminiModel

        agent = build_agent(
            provider="gemini",
            config=self._minimal_config(model="gemini-2.5-flash"),
            tools=[],
            history=[],
            callback_handler=None,
            gemini_api_key="test-key",
        )

        assert isinstance(agent.model, GeminiModel)

    def test_gemini_without_key_falls_back_to_ollama(self):
        from services.strands_provider import build_agent
        from strands.models.ollama import OllamaModel

        agent = build_agent(
            provider="gemini",
            config=self._minimal_config(),
            tools=[],
            history=[],
            callback_handler=None,
            gemini_api_key="",  # no key → fallback
        )

        assert isinstance(agent.model, OllamaModel)

    def test_system_prompt_is_set(self):
        from services.strands_provider import build_agent

        agent = build_agent(
            provider="ollama",
            config=self._minimal_config(),
            tools=[],
            history=[],
            callback_handler=None,
        )

        assert agent.system_prompt == "You are helpful."

    def test_history_is_pre_loaded(self):
        from services.strands_provider import build_agent

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "agent", "content": "Hi there"},
        ]
        agent = build_agent(
            provider="ollama",
            config=self._minimal_config(),
            tools=[],
            history=history,
            callback_handler=None,
        )

        # Two history messages should be pre-loaded
        assert len(agent.messages) == 2
        assert agent.messages[0]["role"] == "user"
        assert agent.messages[1]["role"] == "assistant"

    def test_empty_history_gives_empty_messages(self):
        from services.strands_provider import build_agent

        agent = build_agent(
            provider="ollama",
            config=self._minimal_config(),
            tools=[],
            history=[],
            callback_handler=None,
        )

        assert agent.messages == []


class TestHistoryToStrandsMessages:
    def test_maps_user_role(self):
        from services.strands_provider import _history_to_strands_messages

        result = _history_to_strands_messages([{"role": "user", "content": "Hello"}])

        assert result == [{"role": "user", "content": [{"text": "Hello"}]}]

    def test_maps_agent_role_to_assistant(self):
        from services.strands_provider import _history_to_strands_messages

        result = _history_to_strands_messages([{"role": "agent", "content": "Hi"}])

        assert result == [{"role": "assistant", "content": [{"text": "Hi"}]}]

    def test_skips_empty_content(self):
        from services.strands_provider import _history_to_strands_messages

        result = _history_to_strands_messages([
            {"role": "user", "content": ""},
            {"role": "user", "content": "  "},
            {"role": "user", "content": "Real message"},
        ])

        assert len(result) == 1
        assert result[0]["content"][0]["text"] == "Real message"
