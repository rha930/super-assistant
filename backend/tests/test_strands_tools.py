"""Unit tests for strands_tools factory functions."""

import json
from unittest.mock import MagicMock, patch

from services.strands_tools import (
    build_describe_pins_tool,
    build_fly_to_location_tool,
    build_generate_graph_tool,
    build_news_search_tool,
    build_place_pin_tool,
)

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


# ---------------------------------------------------------------------------
# fly_to_location tool
# ---------------------------------------------------------------------------


def _nominatim_hit(lat="51.5074", lon="-0.1278", display_name="London, UK", osm_type="city"):
    return {"lat": lat, "lon": lon, "display_name": display_name, "type": osm_type}


class TestFlyToLocationTool:
    def _make_tool(self, store=None):
        return build_fly_to_location_tool(store if store is not None else [])

    def test_coordinate_string_bypasses_nominatim(self):
        store: list = []
        tool_fn = self._make_tool(store)
        with patch("services.strands_tools.requests.get") as mock_get:
            result = tool_fn(place="51.5, -0.1")
        mock_get.assert_not_called()
        assert len(store) == 1
        assert store[0]["type"] == "map_action"
        assert store[0]["lat"] == 51.5
        assert store[0]["lng"] == -0.1
        assert "flying" in result.lower()

    def test_place_name_calls_nominatim_and_emits_artifact(self):
        store: list = []
        tool_fn = self._make_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [_nominatim_hit()]
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp) as mock_get:
            result = tool_fn(place="London")
        mock_get.assert_called_once()
        call_params = mock_get.call_args.kwargs.get("params") or mock_get.call_args[1].get("params") or {}
        assert call_params.get("q") == "London"
        assert len(store) == 1
        assert store[0]["action"] == "fly_to"
        assert store[0]["lat"] == 51.5074
        assert "London" in result

    def test_returns_error_string_when_no_results(self):
        store: list = []
        tool_fn = self._make_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp):
            result = tool_fn(place="Xyz123Nonexistent")
        assert "could not find" in result.lower()
        assert len(store) == 0

    def test_returns_error_string_on_network_exception(self):
        store: list = []
        tool_fn = self._make_tool(store)
        with patch("services.strands_tools.requests.get", side_effect=Exception("timeout")):
            result = tool_fn(place="London")
        assert "unavailable" in result.lower() or "failed" in result.lower() or "geocod" in result.lower()
        assert len(store) == 0

    def test_caps_place_at_500_chars(self):
        store: list = []
        tool_fn = self._make_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [_nominatim_hit()]
        mock_resp.raise_for_status.return_value = None
        long_place = "a" * 600
        with patch("services.strands_tools.requests.get", return_value=mock_resp) as mock_get:
            tool_fn(place=long_place)
        actual_q = (mock_get.call_args.kwargs.get("params") or {}).get("q", "")
        assert len(actual_q) == 500

    def test_uses_caller_zoom_when_valid(self):
        store: list = []
        tool_fn = self._make_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [_nominatim_hit()]
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp):
            tool_fn(place="London", zoom=15)
        assert store[0]["zoom"] == 15

    def test_auto_selects_zoom_from_osm_type(self):
        store: list = []
        tool_fn = self._make_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [_nominatim_hit(osm_type="country")]
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp):
            tool_fn(place="France", zoom=0)
        assert store[0]["zoom"] == 5  # country → 5

    def test_rejects_out_of_range_coordinates_from_nominatim(self):
        store: list = []
        tool_fn = self._make_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [_nominatim_hit(lat="999", lon="999")]
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp):
            result = tool_fn(place="Nowhere")
        assert "out-of-range" in result.lower() or "coordinate" in result.lower()
        assert len(store) == 0


# ---------------------------------------------------------------------------
# place_pin tool
# ---------------------------------------------------------------------------


class TestPlacePinTool:
    def _hit(self, lat="48.8584", lon="2.2945", name="Eiffel Tower, Paris", osm_type="tourism"):
        return {"lat": lat, "lon": lon, "display_name": name, "type": osm_type}

    def test_place_name_calls_nominatim_and_emits_add_pin_artifact(self):
        store: list = []
        tool_fn = build_place_pin_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [self._hit()]
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp):
            result = tool_fn(place="Eiffel Tower")
        assert len(store) == 1
        assert store[0]["action"] == "add_pin"
        assert store[0]["lat"] == 48.8584
        assert "Eiffel Tower" in result

    def test_coordinate_string_bypasses_nominatim(self):
        store: list = []
        tool_fn = build_place_pin_tool(store)
        with patch("services.strands_tools.requests.get") as mock_get:
            tool_fn(place="51.5, -0.1")
        mock_get.assert_not_called()
        assert store[0]["lat"] == 51.5

    def test_uses_caller_label_when_non_empty(self):
        store: list = []
        tool_fn = build_place_pin_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [self._hit()]
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp):
            tool_fn(place="Eiffel Tower", label="My pin")
        assert store[0]["label"] == "My pin"

    def test_falls_back_to_resolved_name_when_label_empty(self):
        store: list = []
        tool_fn = build_place_pin_tool(store)
        mock_resp = MagicMock()
        mock_resp.json.return_value = [self._hit(name="Eiffel Tower, Paris, France")]
        mock_resp.raise_for_status.return_value = None
        with patch("services.strands_tools.requests.get", return_value=mock_resp):
            tool_fn(place="Eiffel Tower", label="")
        assert "Eiffel" in store[0]["label"]


# ---------------------------------------------------------------------------
# describe_pins tool
# ---------------------------------------------------------------------------


class TestDescribePinsTool:
    def _make_reverse_resp(self, country="France", city="Paris", state="Île-de-France"):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "address": {"city": city, "state": state, "country": country},
            "display_name": f"{city}, {state}, {country}",
        }
        return resp

    def test_reverse_geocodes_each_pin_and_returns_descriptions(self):
        tool_fn = build_describe_pins_tool()
        pins = [{"label": "Pin A", "lat": 48.86, "lng": 2.35}]
        with patch("services.strands_tools.requests.get", return_value=self._make_reverse_resp()):
            result = tool_fn(pins_json=json.dumps(pins))
        assert "Pin A" in result
        assert "France" in result

    def test_returns_error_string_for_invalid_json(self):
        tool_fn = build_describe_pins_tool()
        result = tool_fn(pins_json="not json [[[")
        assert "not valid json" in result.lower()

    def test_caps_at_20_pins(self):
        tool_fn = build_describe_pins_tool()
        many = [{"label": f"P{i}", "lat": float(i), "lng": 0.0} for i in range(30)]
        calls = []

        def fake_get(*args, **kwargs):
            calls.append(1)
            return self._make_reverse_resp()

        with patch("services.strands_tools.requests.get", side_effect=fake_get):
            tool_fn(pins_json=json.dumps(many))
        assert len(calls) == 20

    def test_individual_failure_returns_location_unknown_for_that_pin(self):
        tool_fn = build_describe_pins_tool()
        pins = [
            {"label": "Good", "lat": 48.86, "lng": 2.35},
            {"label": "Bad", "lat": 0.0, "lng": 0.0},
        ]
        good_resp = self._make_reverse_resp()
        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = Exception("network error")
        with patch("services.strands_tools.requests.get", side_effect=[good_resp, bad_resp]):
            result = tool_fn(pins_json=json.dumps(pins))
        assert "Good" in result
        assert "Bad" in result
        assert "unknown" in result.lower()
