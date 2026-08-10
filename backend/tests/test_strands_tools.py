"""Unit tests for strands_tools factory functions."""

import json
from unittest.mock import MagicMock, patch

from services.strands_tools import (
    build_database_query_tool,
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


# ---------------------------------------------------------------------------
# database_query tool
# ---------------------------------------------------------------------------


class TestDatabaseQueryTool:
    def _make_service(self, *, result=None, raise_exc=None):
        svc = MagicMock()
        if raise_exc is not None:
            svc.execute_read_only_query.side_effect = raise_exc
        else:
            svc.execute_read_only_query.return_value = result or {
                "columns": ["id", "name"],
                "rows": [[1, "Alice"], [2, "Bob"]],
                "row_count": 2,
                "truncated": False,
            }
        return svc

    def test_returns_formatted_table_on_success(self):
        tool_fn = build_database_query_tool(self._make_service())
        result = tool_fn(connector_name="analytics", sql="SELECT id, name FROM users")
        assert "id | name" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "2 row(s)" in result

    def test_zero_rows_message(self):
        svc = self._make_service(result={"columns": ["id"], "rows": [], "row_count": 0, "truncated": False})
        tool_fn = build_database_query_tool(svc)
        result = tool_fn(connector_name="analytics", sql="SELECT id FROM users WHERE 1=0")
        assert "0 rows" in result

    def test_truncation_note_included(self):
        svc = self._make_service(result={"columns": ["id"], "rows": [[1]], "row_count": 1, "truncated": True})
        tool_fn = build_database_query_tool(svc)
        result = tool_fn(connector_name="analytics", sql="SELECT id FROM users")
        assert "truncated" in result.lower()

    def test_unknown_connector_returns_error_string_not_exception(self):
        svc = self._make_service(raise_exc=ValueError("Unknown database connector 'nope'."))
        tool_fn = build_database_query_tool(svc)
        result = tool_fn(connector_name="nope", sql="SELECT 1")
        assert isinstance(result, str)
        assert "rejected" in result.lower()

    def test_non_select_returns_error_string(self):
        svc = self._make_service(raise_exc=ValueError("Only read-only SELECT queries are permitted."))
        tool_fn = build_database_query_tool(svc)
        result = tool_fn(connector_name="analytics", sql="DELETE FROM users")
        assert isinstance(result, str)
        assert "rejected" in result.lower()

    def test_missing_inputs_return_error_strings(self):
        tool_fn = build_database_query_tool(self._make_service())
        assert "connector" in tool_fn(connector_name="", sql="SELECT 1").lower()
        assert "sql" in tool_fn(connector_name="analytics", sql="").lower()

    def test_activity_sink_records_success_details(self):
        sink: list = []
        tool_fn = build_database_query_tool(self._make_service(), activity_sink=sink)
        tool_fn(connector_name="analytics", sql="SELECT id FROM users")
        assert len(sink) == 1
        record = sink[0]
        assert record["name"] == "database_query"
        assert record["status"] == "success"
        assert record["inputs"] == {"connector_name": "analytics", "sql": "SELECT id FROM users"}
        assert record["outputs"] == {"row_count": 2, "truncated": False}
        assert isinstance(record["duration"], int)

    def test_activity_sink_records_error_without_rows(self):
        sink: list = []
        svc = self._make_service(raise_exc=ValueError("bad"))
        tool_fn = build_database_query_tool(svc, activity_sink=sink)
        tool_fn(connector_name="analytics", sql="DELETE FROM users")
        assert sink[0]["status"] == "error"
        assert sink[0]["outputs"] == {"row_count": 0, "truncated": False}
