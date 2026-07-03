import json
import re
import uuid
from typing import Any


class GraphArtifactService:
    """Creates validated graph artifacts from user intent and available data in model output."""

    SUPPORTED_CHART_TYPES = {"line", "bar", "pie"}

    def should_generate_graph(self, user_message: str, agent_response: str) -> bool:
        text = f"{user_message} {agent_response}".lower()
        visualization_keywords = [
            "plot",
            "chart",
            "graph",
            "visualize",
            "trend",
            "compare",
            "comparison",
            "distribution",
            "histogram",
            "line chart",
            "bar chart",
            "pie chart",
        ]
        return any(keyword in text for keyword in visualization_keywords)

    def create_graph_artifacts(self, user_message: str, agent_response: str) -> list[dict[str, Any]]:
        """
        Attempt to build graph artifacts from the model response.

        Heuristic strategy:
        - Detect graph intent from user prompt/response.
        - Parse simple labeled numeric series from response lines.
        - Emit schema-compliant graph artifact when valid data is present.
        """
        # 1) Prefer explicit graph artifacts serialized by the model.
        explicit_artifacts = self._extract_explicit_graph_artifacts(agent_response)
        if explicit_artifacts:
            return explicit_artifacts

        has_graph_intent = self.should_generate_graph(user_message, agent_response)

        # 2) Parse labeled data points from free-form response text.
        points = self._extract_points(agent_response)
        if len(points) >= 2 and (has_graph_intent or self._looks_like_series(points)):
            chart_type = self._infer_chart_type(user_message, agent_response)
            title = self._infer_title(user_message, chart_type)

            graph = {
                "id": f"graph_{uuid.uuid4().hex[:10]}",
                "title": title,
                "chartType": chart_type,
                "xLabel": "Category",
                "yLabel": "Value",
                "series": [{"name": "Series 1", "data": points}],
                "options": {"showLegend": True, "stacked": False},
            }

            if self._validate_graph(graph):
                return [{"type": "graph", "graph": graph}]

        # 3) Last-resort numeric fallback only when user clearly asked for visualization.
        if not has_graph_intent:
            return []

        if len(points) < 2:
            points = self._extract_fallback_numeric_points(agent_response)

        if len(points) < 2:
            return []

        chart_type = self._infer_chart_type(user_message, agent_response)
        title = self._infer_title(user_message, chart_type)

        graph = {
            "id": f"graph_{uuid.uuid4().hex[:10]}",
            "title": title,
            "chartType": chart_type,
            "xLabel": "Category",
            "yLabel": "Value",
            "series": [{"name": "Series 1", "data": points}],
            "options": {"showLegend": True, "stacked": False},
        }

        if not self._validate_graph(graph):
            return []

        return [{"type": "graph", "graph": graph}]

    def _extract_points(self, text: str) -> list[dict[str, Any]]:
        """
        Extract x/y points from common response formats, for example:
        - "Jan: 120"
        - "Q1 - 400"
        - "Product A = 32"
        """
        points: list[dict[str, Any]] = []

        patterns = [
            r"^\s*([A-Za-z0-9 _\-/\.]+)\s*[:=\-]\s*(-?\d+(?:\.\d+)?)\s*$",
            r"^\s*([A-Za-z0-9 _\-/\.]+)\s+(-?\d+(?:\.\d+)?)\s*$",
        ]

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    x_value = match.group(1).strip()
                    y_raw = match.group(2)
                    try:
                        y_value = float(y_raw)
                        points.append({"x": x_value, "y": y_value})
                    except ValueError:
                        pass
                    break

        return points

    def _looks_like_series(self, points: list[dict[str, Any]]) -> bool:
        if len(points) < 3:
            return False

        x_values = [str(p.get("x", "")).strip() for p in points]
        non_empty = [x for x in x_values if x]
        return len(non_empty) >= 3 and len(set(non_empty)) >= 2

    def _extract_explicit_graph_artifacts(self, text: str) -> list[dict[str, Any]]:
        """Extract graph artifacts when model returns structured JSON blocks."""
        artifacts: list[dict[str, Any]] = []

        # Pattern A: fenced JSON blocks
        fenced_blocks = re.findall(r"```json\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", text, flags=re.IGNORECASE)
        for block in fenced_blocks:
            artifacts.extend(self._parse_json_candidate(block))

        # Pattern B: XML-style wrapper for explicit artifacts
        wrapped_blocks = re.findall(r"<graph_artifact>([\s\S]*?)</graph_artifact>", text, flags=re.IGNORECASE)
        for block in wrapped_blocks:
            artifacts.extend(self._parse_json_candidate(block))

        # Deduplicate by graph id
        seen = set()
        unique_artifacts: list[dict[str, Any]] = []
        for artifact in artifacts:
            graph = artifact.get("graph", {}) if isinstance(artifact, dict) else {}
            graph_id = graph.get("id")
            if graph_id and graph_id not in seen:
                seen.add(graph_id)
                unique_artifacts.append(artifact)

        return unique_artifacts

    def _parse_json_candidate(self, raw: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            parsed = json.loads(raw)
        except Exception:
            return results

        candidates = parsed if isinstance(parsed, list) else [parsed]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            if candidate.get("type") == "graph" and isinstance(candidate.get("graph"), dict):
                graph = candidate["graph"]
            elif "chartType" in candidate and "series" in candidate:
                graph = candidate
            else:
                continue

            graph_obj = {
                "id": graph.get("id") or f"graph_{uuid.uuid4().hex[:10]}",
                "title": graph.get("title") or "Generated Chart",
                "chartType": graph.get("chartType") or "line",
                "xLabel": graph.get("xLabel", "Category"),
                "yLabel": graph.get("yLabel", "Value"),
                "series": graph.get("series", []),
                "options": graph.get("options", {"showLegend": True, "stacked": False}),
            }

            if self._validate_graph(graph_obj):
                results.append({"type": "graph", "graph": graph_obj})

        return results

    def _extract_fallback_numeric_points(self, text: str) -> list[dict[str, Any]]:
        """Fallback extractor that maps discovered numbers to indexed categories."""
        numeric_matches = re.findall(r"-?\d+(?:\.\d+)?", text)
        if len(numeric_matches) < 2:
            return []

        points: list[dict[str, Any]] = []
        for idx, raw in enumerate(numeric_matches[:20], start=1):
            try:
                points.append({"x": f"Point {idx}", "y": float(raw)})
            except ValueError:
                continue

        return points

    def _infer_chart_type(self, user_message: str, agent_response: str) -> str:
        text = f"{user_message} {agent_response}".lower()
        if "pie" in text:
            return "pie"
        if "bar" in text or "compare" in text or "comparison" in text:
            return "bar"
        return "line"

    def _infer_title(self, user_message: str, chart_type: str) -> str:
        cleaned = user_message.strip().rstrip("?.!")
        if cleaned:
            return cleaned[:80]
        return f"Generated {chart_type.title()} Chart"

    def _validate_graph(self, graph: dict[str, Any]) -> bool:
        if not isinstance(graph.get("id"), str) or not graph["id"].strip():
            return False
        if not isinstance(graph.get("title"), str) or not graph["title"].strip():
            return False
        if graph.get("chartType") not in self.SUPPORTED_CHART_TYPES:
            return False

        series = graph.get("series")
        if not isinstance(series, list) or len(series) == 0:
            return False

        for item in series:
            if not isinstance(item, dict):
                return False
            data = item.get("data")
            if not isinstance(data, list) or len(data) == 0:
                return False
            for point in data:
                if not isinstance(point, dict):
                    return False
                if "x" not in point or "y" not in point:
                    return False
                if not isinstance(point["x"], str | int | float):
                    return False
                if not isinstance(point["y"], int | float):
                    return False

        return True
