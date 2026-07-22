"""Tests for the GNews news articles tool."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from services.gnews_service import GNewsService

GNEWS_CONFIG = {
    "enabled": True,
    "max_results": 5,
    "language": "en",
    "country": "us",
    "timeout_seconds": 10,
}

SAMPLE_API_RESPONSE = {
    "totalArticles": 2,
    "articles": [
        {
            "title": "First headline",
            "description": "First description",
            "url": "https://example.test/1",
            "publishedAt": "2026-07-15T10:00:00Z",
            "source": {"name": "Example News"},
        },
        {
            "title": "Second headline",
            "description": "Second description",
            "url": "https://example.test/2",
            "publishedAt": "2026-07-15T09:00:00Z",
            "source": {"name": "Other News"},
        },
    ],
}


class TestGNewsServiceAvailability:
    def test_unavailable_without_key(self):
        svc = GNewsService(GNEWS_CONFIG, api_key="")
        assert svc.is_available() is False

    def test_unavailable_when_disabled(self):
        cfg = {**GNEWS_CONFIG, "enabled": False}
        svc = GNewsService(cfg, api_key="key")
        assert svc.is_available() is False

    def test_available_with_key_and_enabled(self):
        svc = GNewsService(GNEWS_CONFIG, api_key="key")
        assert svc.is_available() is True


class TestGNewsServiceSearch:
    def test_search_raises_when_unavailable(self):
        svc = GNewsService(GNEWS_CONFIG, api_key="")
        with pytest.raises(RuntimeError):
            svc.search("anything")

    def test_search_empty_query_raises_value_error(self):
        svc = GNewsService(GNEWS_CONFIG, api_key="key")
        with pytest.raises(ValueError):
            svc.search("   ")

    def test_search_too_long_query_raises_value_error(self):
        svc = GNewsService(GNEWS_CONFIG, api_key="key")
        with pytest.raises(ValueError):
            svc.search("a" * 501)

    @patch("services.gnews_service.requests.get")
    def test_search_success_returns_shaped_articles(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_API_RESPONSE
        mock_get.return_value = mock_response

        svc = GNewsService(GNEWS_CONFIG, api_key="key")
        result = svc.search("climate")

        assert result["total_articles"] == 2
        assert len(result["articles"]) == 2
        first = result["articles"][0]
        assert first == {
            "title": "First headline",
            "description": "First description",
            "url": "https://example.test/1",
            "source": "Example News",
            "published_at": "2026-07-15T10:00:00Z",
        }

    @patch("services.gnews_service.requests.get")
    def test_search_passes_api_key_as_token(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"totalArticles": 0, "articles": []}
        mock_get.return_value = mock_response

        svc = GNewsService(GNEWS_CONFIG, api_key="secret-key")
        svc.search("news")

        _, kwargs = mock_get.call_args
        assert kwargs["params"]["token"] == "secret-key"
        assert kwargs["params"]["q"] == "news"

    @patch("services.gnews_service.requests.get")
    def test_search_http_error_raises_without_leaking_key(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        svc = GNewsService(GNEWS_CONFIG, api_key="secret-key")
        with pytest.raises(RuntimeError) as exc_info:
            svc.search("news")

        assert "secret-key" not in str(exc_info.value)
        assert "401" in str(exc_info.value)

    @patch("services.gnews_service.requests.get")
    def test_search_timeout_raises_runtime_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()

        svc = GNewsService(GNEWS_CONFIG, api_key="secret-key")
        with pytest.raises(RuntimeError) as exc_info:
            svc.search("news")

        assert "secret-key" not in str(exc_info.value)


class TestAgentNewsIntegration:
    def test_wants_news_detects_keywords(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        assert agent._wants_news("what's the latest news on AI?") is True
        assert agent._wants_news("tell me a joke") is False

    def test_wants_news_detects_broader_phrasings(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        assert agent._wants_news("what happened in the election") is True
        assert agent._wants_news("any updates on the mars mission") is True
        assert agent._wants_news("show me today's headlines") is True
        assert agent._wants_news("what's going on with the stock market") is True
        assert agent._wants_news("write me a poem about the ocean") is False

    def test_build_news_query_strips_filler(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        assert agent._build_news_query("what's the latest news about the AI industry") == "ai industry"
        assert agent._build_news_query("show me today's headlines on climate change") == "climate change"

    def test_build_news_query_falls_back_to_original(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        # All words are stopwords/triggers -> fall back to original text.
        assert agent._build_news_query("latest news today") == "latest news today"

    def test_maybe_fetch_news_uses_cleaned_query(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        gnews = MagicMock()
        gnews.is_available.return_value = True
        gnews.search.return_value = {"articles": [], "total_articles": 0}

        agent._maybe_fetch_news("what's the latest news about climate change", gnews)
        gnews.search.assert_called_once_with("climate change")

    def test_maybe_fetch_news_records_tool_call(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        gnews = MagicMock()
        gnews.is_available.return_value = True
        gnews.search.return_value = {
            "articles": [
                {
                    "title": "T",
                    "description": "D",
                    "url": "https://example.test/1",
                    "source": "S",
                    "published_at": "2026-07-15T10:00:00Z",
                }
            ],
            "total_articles": 1,
        }

        context, tool_call = agent._maybe_fetch_news("latest news about AI", gnews)
        assert context is not None
        assert tool_call["name"] == "news_search"
        assert tool_call["status"] == "success"
        assert tool_call["outputs"]["article_count"] == 1

    def test_maybe_fetch_news_skips_when_unavailable(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        gnews = MagicMock()
        gnews.is_available.return_value = False

        context, tool_call = agent._maybe_fetch_news("latest news about AI", gnews)
        assert context is None
        assert tool_call is None

    def test_maybe_fetch_news_error_records_error_tool_call(self):
        from services.strands_agent import StrandsAgentService

        agent = StrandsAgentService()
        gnews = MagicMock()
        gnews.is_available.return_value = True
        gnews.search.side_effect = RuntimeError("boom")

        context, tool_call = agent._maybe_fetch_news("latest news about AI", gnews)
        assert context is None
        assert tool_call["status"] == "error"
