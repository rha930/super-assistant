"""Strands @tool factory functions for the AERIAL agent.

Each public function returns a properly decorated @tool that the Strands
Agent can call during its reasoning loop. Factories accept service
dependencies via closure so tool functions remain stateless primitives with
plain-type signatures (required by the SDK's schema generator).
"""

import json
import logging
import os
import re
import uuid
from typing import Any

import requests
from strands import tool as strands_tool

logger = logging.getLogger(__name__)

_MAX_QUERY_LENGTH = 500
_MAX_SERIES_JSON_BYTES = 8_192
_ALLOWED_CHART_TYPES = frozenset({"line", "bar", "pie"})

_COORD_RE = re.compile(r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$")
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_HEADERS = {"User-Agent": "AERIAL-App/1.0"}
_NOMINATIM_TIMEOUT = 8
# Allow disabling SSL verification for environments behind SSL-inspecting proxies
_NOMINATIM_VERIFY_SSL = os.getenv("NOMINATIM_VERIFY_SSL", "true").lower() != "false"

_ZOOM_BY_TYPE: dict[str, int] = {
    "continent": 3,
    "country": 5,
    "state": 7,
    "county": 9,
    "city": 10,
    "town": 12,
    "village": 13,
    "suburb": 14,
    "neighbourhood": 15,
    "building": 17,
}


def _zoom_for_type(osm_type: str | None) -> int:
    return _ZOOM_BY_TYPE.get(osm_type or "", 10)


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
            lines.append(f"{i}. {title} — {source} ({published})\n   {description}\n   {url}")
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
            return f"Invalid chart_type '{chart_type}'. Must be one of: {', '.join(sorted(_ALLOWED_CHART_TYPES))}."

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


def build_fly_to_location_tool(artifact_store: list):
    """Return a @tool that navigates the map panel to a named place or coordinates."""

    def fly_to_location(place: str, zoom: int = 0) -> str:
        """Navigate the map panel to a specific location by place name or coordinates.

        Use this when the user asks to show, navigate to, zoom in on, fly to,
        or go to a specific place on the map. The map panel will animate to the
        location automatically.

        place: a place name ("London", "Amazon rainforest", "Eiffel Tower") or
               decimal coordinates as "lat, lng" (e.g. "48.8566, 2.3522").
        zoom:  optional zoom level 1–19. If 0 or omitted the tool picks a
               sensible default based on the place type (country=5, city=10,
               neighbourhood=15, etc.).

        After calling this tool you MUST respond to the user with a short
        confirmation such as "I've navigated the map to [place]. Is there
        anything you'd like to know about this area?" — never leave the
        response blank after a fly_to_location call.
        """
        place = place.strip()[:500]
        if not place:
            return "No place specified."

        # Try direct coordinate parse first — avoids a network call
        coord_match = _COORD_RE.match(place)
        if coord_match:
            lat = round(float(coord_match.group(1)), 6)
            lng = round(float(coord_match.group(2)), 6)
            resolved = place
            osm_type = None
        else:
            try:
                resp = requests.get(
                    _NOMINATIM_URL,
                    params={"q": place, "format": "json", "limit": 1},
                    headers=_NOMINATIM_HEADERS,
                    timeout=_NOMINATIM_TIMEOUT,
                    verify=_NOMINATIM_VERIFY_SSL,
                )
                resp.raise_for_status()
                results = resp.json()
            except Exception as exc:
                logger.warning("Nominatim geocoding failed for %r: %s", place, exc)
                return f"Could not geocode '{place}': geocoding service unavailable."

            if not results:
                return f"Could not find a location matching '{place}'."

            hit = results[0]
            try:
                lat = round(float(hit["lat"]), 6)
                lng = round(float(hit["lon"]), 6)
            except (KeyError, ValueError, TypeError):
                return f"Geocoding returned an unreadable coordinate for '{place}'."

            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                return f"Geocoding returned an out-of-range coordinate for '{place}'."

            resolved = str(hit.get("display_name", place))
            osm_type = hit.get("type") or hit.get("addresstype")

        effective_zoom = zoom if 1 <= zoom <= 19 else _zoom_for_type(osm_type)
        artifact_store.append(
            {
                "type": "map_action",
                "action": "fly_to",
                "lat": lat,
                "lng": lng,
                "zoom": effective_zoom,
                "place_name": resolved[:200],
            }
        )
        short = resolved[:80]
        return f"Flying to {short} (lat={lat}, lng={lng}) at zoom {effective_zoom}."

    return strands_tool(fly_to_location)
