"""Unit tests for strands_tools factory functions."""

import json
from unittest.mock import MagicMock

from services.strands_tools import build_generate_graph_tool, build_news_search_tool

# ---------------------------------------------------------------------------
# news_search tool
# ---------------------------------------------------------------------------


class TestNewsSearchTool:
    def _make_gnews(self, *, available=True, articles=None, raise_exc=None):
        svc = MagicMock()
        svc.is_available.return_value = available
        if raise_exc:
            svc.search.side_effect = raise_exc
        else:
            svc.search.return_value = {"articles": articles or []}
        return svc

    def test_returns_formatted_articles(self):
        articles = [
            {
                "title": "Headline One",
                "source": "Reuters",
                "published_at": "2026-01-01",
                "description": "Summary one.",
                "url": "https://reuters.com/1",
            }
        ]
        gnews = self._make_gnews(articles=articles)
        tool_fn = build_news_search_tool(gnews)

        result = tool_fn(query="AI news")

        assert "Headline One" in result
        assert "Reuters" in result
        assert "Summary one." in result
        gnews.search.assert_called_once_with("AI news")

    def test_returns_informative_string_when_unavailable(self):
        gnews = self._make_gnews(available=False)
        tool_fn = build_news_search_tool(gnews)

        result = tool_fn(query="news")

        assert "not available" in result.lower()
        gnews.search.assert_not_called()

    def test_returns_informative_string_when_no_articles(self):
        gnews = self._make_gnews(articles=[])
        tool_fn = build_news_search_tool(gnews)

        result = tool_fn(query="obscure topic xyz")

        assert "no recent" in result.lower() or "not found" in result.lower()

    def test_returns_error_string_does_not_raise_on_exception(self):
        gnews = self._make_gnews(raise_exc=RuntimeError("timeout"))
        tool_fn = build_news_search_tool(gnews)

        result = tool_fn(query="something")

        assert "failed" in result.lower()
        # Must NOT raise

    def test_truncates_query_over_500_chars(self):
        gnews = self._make_gnews(articles=[])
        tool_fn = build_news_search_tool(gnews)
        long_query = "a" * 600

        tool_fn(query=long_query)

        actual_query = gnews.search.call_args[0][0]
        assert len(actual_query) == 500

    def test_none_gnews_service_returns_unavailable(self):
        tool_fn = build_news_search_tool(None)

        result = tool_fn(query="news")

        assert "not available" in result.lower()


# ---------------------------------------------------------------------------
# generate_graph tool
# ---------------------------------------------------------------------------


class TestGenerateGraphTool:
    def _valid_series(self):
        return json.dumps([{"name": "S1", "data": [{"x": "A", "y": 10}, {"x": "B", "y": 20}]}])

    def test_appends_artifact_and_returns_confirmation(self):
        store: list = []
        tool_fn = build_generate_graph_tool(store)

        result = tool_fn(
            title="Sales Chart",
            chart_type="bar",
            x_label="Month",
            y_label="Revenue",
            series_json=self._valid_series(),
        )

        assert len(store) == 1
        artifact = store[0]
        assert artifact["type"] == "graph"
        assert artifact["graph"]["title"] == "Sales Chart"
        assert artifact["graph"]["chartType"] == "bar"
        assert "Sales Chart" in result

    def test_returns_error_for_invalid_chart_type(self):
        store: list = []
        tool_fn = build_generate_graph_tool(store)

        result = tool_fn(
            title="Bad",
            chart_type="scatter",
            x_label="X",
            y_label="Y",
            series_json=self._valid_series(),
        )

        assert "scatter" in result
        assert len(store) == 0  # no artifact stored

    def test_returns_error_for_invalid_json(self):
        store: list = []
        tool_fn = build_generate_graph_tool(store)

        result = tool_fn(
            title="Bad",
            chart_type="line",
            x_label="X",
            y_label="Y",
            series_json="not json {{{",
        )

        assert "not valid json" in result.lower()
        assert len(store) == 0

    def test_returns_error_for_oversized_series_json(self):
        store: list = []
        tool_fn = build_generate_graph_tool(store)
        huge = json.dumps([{"name": "S", "data": [{"x": str(i), "y": i} for i in range(10_000)]}])

        result = tool_fn(
            title="Huge",
            chart_type="line",
            x_label="X",
            y_label="Y",
            series_json=huge,
        )

        assert "maximum" in result.lower() or "size" in result.lower()
        assert len(store) == 0

    def test_graph_artifact_has_unique_id(self):
        store: list = []
        tool_fn = build_generate_graph_tool(store)

        tool_fn(title="G1", chart_type="pie", x_label="", y_label="", series_json=self._valid_series())
        tool_fn(title="G2", chart_type="pie", x_label="", y_label="", series_json=self._valid_series())

        ids = [a["graph"]["id"] for a in store]
        assert ids[0] != ids[1]

    def test_all_allowed_chart_types_accepted(self):
        for chart_type in ("line", "bar", "pie"):
            store: list = []
            tool_fn = build_generate_graph_tool(store)
            result = tool_fn(
                title="T",
                chart_type=chart_type,
                x_label="X",
                y_label="Y",
                series_json=self._valid_series(),
            )
            assert len(store) == 1, f"Expected artifact for chart_type={chart_type}"
            assert "error" not in result.lower()
