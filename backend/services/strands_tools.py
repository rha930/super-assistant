"""Strands @tool factory functions for the AERIAL agent.

Each public function returns a properly decorated @tool that the Strands
Agent can call during its reasoning loop. Factories accept service
dependencies via closure so tool functions remain stateless primitives with
plain-type signatures (required by the SDK's schema generator).
"""

import json
import logging
import uuid
from typing import Any

from strands import tool as strands_tool

logger = logging.getLogger(__name__)

_MAX_QUERY_LENGTH = 500
_MAX_SERIES_JSON_BYTES = 8_192
_ALLOWED_CHART_TYPES = frozenset({"line", "bar", "pie"})


def build_news_search_tool(gnews_service: Any):
    """Return a @tool that searches recent news via gnews_service."""

    def news_search(query: str) -> str:
        """Search recent news articles for the given query.

        Use this when the user asks about current events, news headlines,
        what is happening, recent developments, breaking news, or any
        live topic that may have changed after the model's training cutoff.

        Returns a formatted list of article titles, sources, and summaries
        that should be used to ground the response.
        """
        if len(query) > _MAX_QUERY_LENGTH:
            query = query[:_MAX_QUERY_LENGTH]

        if not gnews_service or not getattr(gnews_service, "is_available", lambda: False)():
            return "News search is not available (service not configured)."

        try:
            result = gnews_service.search(query)
        except Exception as exc:
            logger.warning("news_search tool failed for query=%r: %s", query, exc)
            return f"News search failed: {exc}"

        articles = (result or {}).get("articles", [])
        if not articles:
            return "No recent news articles found for that query."

        lines = ["Recent news articles:"]
        for i, article in enumerate(articles, 1):
            title = str(article.get("title", "")).strip()
            source = str(article.get("source", "")).strip()
            published = str(article.get("published_at", "")).strip()
            description = str(article.get("description", "")).strip()
            url = str(article.get("url", "")).strip()
            lines.append(
                f"{i}. {title} — {source} ({published})\n"
                f"   {description}\n"
                f"   {url}"
            )
        return "\n".join(lines)

    return strands_tool(news_search)


def build_generate_graph_tool(artifact_store: list):
    """Return a @tool that emits graph artifacts into artifact_store."""

    def generate_graph(
        title: str,
        chart_type: str,
        x_label: str,
        y_label: str,
        series_json: str,
    ) -> str:
        """Emit a chart or graph visualization shown in the Graph Panel.

        Use this when the user asks for a chart, plot, graph, data
        visualization, histogram, or any visual representation of data.

        chart_type must be one of: line, bar, pie.
        series_json must be a JSON array of series objects:
          [{"name": "Series 1", "data": [{"x": "Label", "y": 10}]}]
        x_label and y_label describe the chart axes (ignored for pie charts).
        The y value in each data point must be numeric.

        Returns a confirmation string on success or an error description.
        """
        if chart_type not in _ALLOWED_CHART_TYPES:
            return (
                f"Invalid chart_type '{chart_type}'. "
                f"Must be one of: {', '.join(sorted(_ALLOWED_CHART_TYPES))}."
            )

        if len(series_json.encode()) > _MAX_SERIES_JSON_BYTES:
            return "series_json exceeds the maximum allowed size (8 KB)."

        try:
            series = json.loads(series_json)
        except json.JSONDecodeError as exc:
            return f"series_json is not valid JSON: {exc}"

        if not isinstance(series, list) or not series:
            return "series_json must be a non-empty JSON array."

        graph: dict[str, Any] = {
            "id": f"graph_{uuid.uuid4().hex[:10]}",
            "title": title,
            "chartType": chart_type,
            "xLabel": x_label,
            "yLabel": y_label,
            "series": series,
            "options": {"showLegend": True, "stacked": False},
        }
        artifact_store.append({"type": "graph", "graph": graph})
        return f"Graph '{title}' ({chart_type}) created with {len(series)} series."

    return strands_tool(generate_graph)
