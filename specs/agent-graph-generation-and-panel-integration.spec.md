# Spec: Agent-Generated Graph Creation and Graph Panel Integration

## Purpose
Enable the agent to generate structured graph artifacts from user requests/data and ensure those artifacts are rendered automatically in the frontend Graph Panel.

## Problem Statement
The app has a Graph Panel and a graph artifact contract, but the agent behavior for when and how to generate graph payloads is not fully defined as a product requirement. This leads to inconsistent graph creation and unreliable panel population.

## Goals
- Define when the agent should create graphs.
- Define a strict graph artifact schema the backend must return.
- Ensure frontend reliably validates and displays agent-generated graphs.
- Preserve normal chat responses while adding graph artifacts.

## Non-Goals
- No full BI dashboard builder.
- No complex multi-step chart editing UI.
- No PDF/export pipeline in this feature.

## User Stories
- As a user, I can ask the agent to visualize data and see a graph in the Graph Panel.
- As a user, I can receive both text explanation and chart visualization from one response.
- As a user, if graph generation fails, I get a clear textual explanation and non-crashing UI behavior.

## Functional Requirements
1. Agent must detect visualization intent from prompts (e.g., "plot", "chart", "graph", "trend", "compare").
2. Agent must output graph artifacts when sufficient structured data is available.
3. Graph artifacts must be included in backend chat response under `artifacts`.
4. Response must still include human-readable text summary in `message`.
5. Frontend must validate graph artifacts before rendering.
6. Valid graph artifacts must appear in Graph Panel for active conversation.
7. Multiple graph artifacts in one response must be selectable in Graph Panel.

## Agent Behavior Requirements
1. Graph decision policy:
   - Create graph when user explicitly requests visualization.
   - Create graph when comparative/trend data is central to answer.
   - Avoid graph when data volume/quality is insufficient.
2. If insufficient data:
   - Return text explaining why graph was not generated.
   - Omit invalid/placeholder graph artifacts.
3. Artifact quality:
   - Use meaningful graph title.
   - Use appropriate chart type (`line`, `bar`, `pie`).
   - Include at least one series with valid x/y points.

## Strands Prompt/Instruction Requirements
The agent system instructions should include explicit output guidance:
- When visualization is appropriate, include a graph artifact object.
- Keep text explanation concise and aligned to chart data.
- Only emit supported chart types.
- Ensure numeric y-values and label-safe x-values.

## Backend Requirements
1. Strands service must parse agent output and normalize graph artifact payload.
2. Backend response contract:
   - `message`: textual response
   - `artifacts`: array containing `type: graph` entries
3. In streaming mode:
   - Artifacts must be delivered by final done payload (or a dedicated artifact event) in a deterministic location.
4. Backend must validate/sanitize artifact payload before forwarding to frontend.
5. On validation failure:
   - Do not emit malformed graph artifact.
   - Log structured warning and continue with text response.

## Artifact Contract
### Graph Artifact Envelope
```json
{
  "type": "graph",
  "graph": {
    "id": "graph_001",
    "title": "Revenue by Week",
    "chartType": "line",
    "xLabel": "Week",
    "yLabel": "Revenue",
    "series": [
      {
        "name": "Revenue",
        "data": [
          { "x": "W1", "y": 1200 },
          { "x": "W2", "y": 1500 }
        ]
      }
    ],
    "options": {
      "showLegend": true,
      "stacked": false
    }
  }
}
```

### Validation Rules
- `graph.id`: non-empty string
- `graph.title`: non-empty string
- `graph.chartType`: one of `line | bar | pie`
- `graph.series`: non-empty array
- Each point requires valid `x` and numeric `y`

## Frontend Requirements
1. Chat store must extract graph artifacts from response payload.
2. Graph artifacts must be associated with active conversation ID.
3. Graph Panel must render first valid graph automatically when none selected.
4. Graph selector must allow switching when multiple graphs are present.
5. Invalid artifacts must show safe error state and not crash UI.
6. Graph rendering should remain theme-aware (light/dark).

## Error Handling Requirements
1. Agent returns malformed graph:
   - Backend drops malformed artifact and includes text fallback.
2. Frontend validation fails:
   - Skip artifact rendering, show non-blocking panel warning.
3. No artifacts returned:
   - Graph Panel empty state remains visible.

## Security and Validation
- Treat all artifact payload fields as untrusted input.
- Escape/sanitize labels/titles before rendering.
- Enforce max payload size and point limits server-side.

## Telemetry (Optional)
- Event: `graph_artifact_generated`
  - Properties: `chart_type`, `series_count`, `point_count`, `conversation_id`
- Event: `graph_artifact_rejected`
  - Properties: `reason`, `conversation_id`
- Event: `graph_rendered`
  - Properties: `chart_type`, `conversation_id`

## Acceptance Criteria
1. Asking for a chart with valid data returns text plus graph artifact.
2. Graph artifact appears in Graph Panel without manual refresh.
3. Multiple artifacts are selectable in the panel.
4. Invalid artifacts do not break chat or UI rendering.
5. Streaming and non-streaming chat flows both support graph artifacts.

## Test Cases
- Unit:
  - Artifact validator accepts valid payload and rejects invalid schema.
  - Agent output parser maps graph artifact to response envelope.
- Integration:
  - Prompt: "plot weekly revenue" returns graph artifact and chart renders.
  - Prompt with insufficient data returns text-only response and empty panel state.
  - Multi-graph response supports selector switching.
- Regression:
  - Standard non-graph chat requests still work unchanged.
  - Existing message streaming behavior remains intact.

## Rollout Plan
1. Add/confirm Strands instructions for graph generation.
2. Add backend parsing/validation and artifact attachment.
3. Verify frontend extraction/render path with fixture payloads.
4. Enable telemetry and monitor artifact success/failure rates.

## Implementation Notes
- Reuse existing graph contract documentation in GRAPH_ARTIFACTS.md.
- Keep artifact generation deterministic and schema-first.
- Favor clear text fallback when graph generation confidence is low.
