# Spec: Widget Context Injection — Live Widget State as Agent Context

## Purpose
Give the agent awareness of what the user is currently doing in the open
widgets (Map, Graph, Notes) by injecting a compact, real-time **workspace state
snapshot** into every chat request. The agent can then give spatially,
graphically, or editorially aware answers without the user having to describe
their current view.

## Problem Statement
Today every `/api/chat/stream` request reaches the backend with only the user's
text message and conversation history. The agent has no awareness of:
- Which panel is open (Map, Graph, Notes)
- What the user is looking at (map viewport zoom, placed pins, active graph, open note title)
- What just happened in a widget before the user sent their message

This forces users to type context that the app already knows ("I'm looking at
the map at zoom 10 around Japan…"). The telemetry spec
(`specs/widget-telemetry.spec.md`) captures widget events server-side for
analytics. This spec uses the same event taxonomy but takes a different path:
the frontend embeds a live snapshot of widget state directly in the chat request
payload, allowing the agent to use it on the very next message — with zero
latency and no round-trip to a telemetry store.

## Goals
1. Frontend composes a `widget_context` object on each message send, describing
   the current state of open widgets.
2. `widget_context` is sent alongside `message` and `conversation_id` in the
   existing `POST /api/chat/stream` and `POST /api/chat/message` request bodies.
3. Backend injects `widget_context` into the agent's system prompt as an
   additional context block (similar to how `GNewsService` injects news articles
   today in `strands_agent.py` / `strands_provider.py`).
4. The agent can reference the context naturally ("You're looking at zoom 8
   around Tokyo — here's what's interesting in that region…").
5. No coordinates, note content, message content, or PII are included —
   `widget_context` is strictly structural/positional metadata.
6. `widget_context` is optional; if the frontend sends none or the field is
   absent, the backend behaves identically to today.

## Non-Goals
- No changes to the telemetry SQLite store — this is live injection, not replay
  of stored events.
- No polling or push from backend to frontend — the snapshot is built in the
  frontend at message-send time.
- No agent-initiated map/widget control in this spec (that is the Phase 2 agent
  map-action tool described in `specs/completed/map-view-widget.spec.md` Phase 2
  notes).
- No content is captured: note body, graph series values, map marker labels are
  excluded from `widget_context`.
- No authentication changes; `widget_context` is treated as trusted client-side
  metadata (same trust level as `conversation_id`).

## User Stories
- As a user, I ask "What's interesting near where I'm looking?" and the agent
  describes the current map region without me specifying coordinates.
- As a user, I ask "Explain this chart" while the Graph panel is open and the
  agent knows the chart type and axis labels without me re-describing them.
- As a user, I ask "Help me expand this note" while Notes is open and the agent
  knows the note title without me typing it.
- As a user, I ask anything while no widget is open and the agent answers
  exactly as it does today — no change.

---

## Widget Context Schema

```typescript
interface WidgetContext {
  active_panel: 'map' | 'graph' | 'notes' | 'history' | null
  map?: {
    zoom: number          // current zoom level (integer)
    // No lat/lng — structural only
    point_count: number   // number of user-placed pins
  }
  graph?: {
    chart_count: number       // number of graphs in the panel
    active_chart_type: string | null  // 'line' | 'bar' | 'pie' | null
    active_chart_title: string | null // title of the first/selected graph
  }
  notes?: {
    note_title: string | null   // title of the active note (no body content)
    note_taking_mode: boolean   // whether note-taking mode is active
  }
}
```

Constraints:
- `map.zoom` is an integer rounded to the nearest whole number.
- No map coordinates (center lat/lng) are sent.
- `graph.active_chart_title` is the title string only — no data values or labels.
- `notes.note_title` is the title only — no note body content.
- The entire field is omitted if no widget is open (`active_panel: null` and all
  sub-objects absent is valid but `widget_context` itself may be `null` or
  omitted).

---

## Architecture

### Data flow
```
User sends message in ChatWindow
  → chatStore.sendMessage(message, widget_context)
    → POST /api/chat/stream { message, conversation_id, widget_context }
      → ChatService.stream_message(message, conversation_id, widget_context)
        → _build_widget_context_block(widget_context) → string
          → injected into Agent system prompt
            → Agent response references widget state
```

### Frontend — snapshot composition

A new composable `frontend/src/composables/useWidgetContext.ts` reads live
Pinia store state at call time and returns the snapshot:

```typescript
export function useWidgetContext(): WidgetContext | null {
  const navStore = useNavStore()
  const mapStore = useMapStore()
  const chatStore = useChatStore()
  const notesStore = useNotesStore()

  const panel = navStore.activeModule  // 'graph' | 'notes' | 'map' | null

  if (!panel) return null

  const ctx: WidgetContext = { active_panel: panel }

  if (panel === 'map') {
    ctx.map = {
      zoom: mapStore.lastZoom,
      point_count: mapStore.points.length,
    }
  }

  if (panel === 'graph') {
    const graphs = chatStore.currentGraphs
    ctx.graph = {
      chart_count: graphs.length,
      active_chart_type: graphs[0]?.chartType ?? null,
      active_chart_title: graphs[0]?.title ?? null,
    }
  }

  if (panel === 'notes') {
    ctx.notes = {
      note_title: notesStore.activeNote?.title ?? null,
      note_taking_mode: notesStore.noteTakingMode,
    }
  }

  return ctx
}
```

### Frontend — ChatWindow integration

`ChatWindow.vue` calls `useWidgetContext()` at the moment the user submits a
message and passes the result to `chatStore.sendMessage` / the streaming fetch.
The API call body becomes:

```json
{
  "message": "What's interesting here?",
  "conversation_id": "conv_abc123",
  "widget_context": {
    "active_panel": "map",
    "map": { "zoom": 8, "point_count": 3 }
  }
}
```

### Backend — `ChatService` changes

`ChatService.stream_message` and `process_message` accept an optional
`widget_context: dict | None` parameter (default `None`).

A new private method `_build_widget_context_block(ctx: dict) -> str` converts
the dict to a concise natural-language block:

```
User's current workspace context:
- Active widget: Map
- Map zoom level: 8 (city-level detail)
- User has placed 3 map pins
```

or for Graph:

```
User's current workspace context:
- Active widget: Graph panel
- Graphs displayed: 2
- Primary chart: bar chart titled "Sales by Region"
```

or for Notes:

```
User's current workspace context:
- Active widget: Notes
- Active note: "Meeting agenda"
- Note-taking mode: active (agent responses are being saved to this note)
```

This block is prepended to the agent's system prompt (after the user-configured
`system_prompt` and before history) via the existing prompt construction in
`strands_provider.py` / `build_agent`.

### Backend — `strands_provider.py` changes

`build_agent` gains an optional `widget_context_block: str | None = None`
parameter. When non-empty, it is appended to `system_prompt` before passing to
`Agent(system_prompt=...)`.

---

## Component Map

| File | Change |
|---|---|
| `frontend/src/composables/useWidgetContext.ts` | **New** — snapshot composer |
| `frontend/src/components/ChatWindow.vue` | Call `useWidgetContext()` on send; include in API request |
| `frontend/src/services/api.ts` | No change needed — body is already arbitrary JSON |
| `backend/routes/chat.py` | Extract `widget_context` from request body; pass to `ChatService` |
| `backend/services/chat_service.py` | Accept `widget_context`; call `_build_widget_context_block`; pass block to `build_agent` |
| `backend/services/strands_provider.py` | Accept `widget_context_block`; append to system prompt |

---

## Backend Requirements

### `backend/services/chat_service.py`

```python
def stream_message(self, message, conversation_id=None, user_id="anonymous",
                   widget_context=None):
    ...
    widget_block = self._build_widget_context_block(widget_context)
    agent = self._build_strands_agent(provider, history, artifact_store,
                                      callback_handler,
                                      widget_context_block=widget_block)
    ...

def _build_widget_context_block(self, ctx: dict | None) -> str | None:
    if not ctx or not isinstance(ctx, dict):
        return None
    panel = ctx.get("active_panel")
    if not panel:
        return None

    lines = [f"User's current workspace context:", f"- Active widget: {panel.title()}"]

    if panel == "map" and "map" in ctx:
        m = ctx["map"]
        zoom = int(m.get("zoom", 0))
        detail = _zoom_label(zoom)
        lines.append(f"- Map zoom level: {zoom} ({detail})")
        lines.append(f"- User has placed {m.get('point_count', 0)} map pin(s)")

    elif panel == "graph" and "graph" in ctx:
        g = ctx["graph"]
        lines.append(f"- Graphs displayed: {g.get('chart_count', 0)}")
        if g.get("active_chart_type"):
            lines.append(f"- Primary chart type: {g['active_chart_type']}")
        if g.get("active_chart_title"):
            lines.append(f"- Primary chart title: {g['active_chart_title']}")

    elif panel == "notes" and "notes" in ctx:
        n = ctx["notes"]
        if n.get("note_title"):
            lines.append(f"- Active note: \"{n['note_title']}\"")
        if n.get("note_taking_mode"):
            lines.append(
                "- Note-taking mode is active: the agent's response will be "
                "appended to this note."
            )

    return "\n".join(lines)

def _zoom_label(zoom: int) -> str:
    if zoom <= 3:   return "world/continent view"
    if zoom <= 6:   return "country/region view"
    if zoom <= 9:   return "city-area view"
    if zoom <= 12:  return "neighbourhood view"
    return "street-level view"
```

### `backend/services/strands_provider.py`

```python
def build_agent(provider, config, tools, history, callback_handler, *,
                gemini_api_key="", widget_context_block=None):
    system_prompt = config.get("system_prompt") or "You are a helpful AI assistant."
    if widget_context_block:
        system_prompt = f"{system_prompt}\n\n{widget_context_block}"
    ...
```

### `backend/routes/chat.py`

Extract `widget_context` from the JSON body and pass it to the service:

```python
widget_context = data.get("widget_context")  # dict | None
response = chat_service.stream_message(
    message, conversation_id, user_id=user_id, widget_context=widget_context
)
```

Validation: if `widget_context` is present but not a dict, treat it as `None`
(no error returned to client).

---

## Frontend Requirements

### `frontend/src/composables/useWidgetContext.ts` (new)
- Pure function of store state — no side effects, no async.
- Returns `null` when no panel is active.
- Reads `mapStore.lastZoom` and `mapStore.points.length` for map context.
- Reads `chatStore.currentGraphs` for graph context.
- Reads `notesStore.activeNote?.title` and `notesStore.noteTakingMode` for
  notes context.

### `frontend/src/components/ChatWindow.vue`
- Import `useWidgetContext` composable.
- On message submit (before the `fetch`/store call), call
  `const ctx = useWidgetContext()`.
- Include `widget_context: ctx` in the request body (field is `null` or absent
  when no panel is active — the backend handles both).

---

## Security / Validation
- `widget_context` is read from the request body alongside `message` — same
  trust level as `conversation_id` (client-provided, user-owned).
- The backend never reflects `widget_context` back in any response — it is
  consumed into the system prompt only.
- `_build_widget_context_block` sanitises by extracting only known typed fields
  (`zoom`, `point_count`, `chart_count`, `active_chart_type`,
  `active_chart_title`, `note_title`, `note_taking_mode`) and never writes
  arbitrary string values from the context dict verbatim into the system prompt
  except for `active_chart_title` and `note_title`, which are bounded by length
  (`[:200]` slice) to prevent prompt-injection via a very long title.
- No coordinates, note body, graph data values, or message content appear in the
  context block.

---

## Testing Requirements

### Backend (`cd backend && python -m pytest tests/ -v`)
New file `backend/tests/test_widget_context.py`:
1. `_build_widget_context_block(None)` returns `None`.
2. `_build_widget_context_block({})` returns `None`.
3. Map context block contains zoom label and point count; does not contain
   coordinate strings.
4. Graph context block contains chart count, type, and title.
5. Notes context block contains note title; when `note_taking_mode=True`,
   includes the note-taking mode sentence.
6. Long `active_chart_title` / `note_title` are truncated to 200 chars in the
   output.
7. `build_agent` with `widget_context_block` appends the block to the system
   prompt passed to `Agent`.
8. `build_agent` with `widget_context_block=None` uses the system prompt
   unchanged.
9. `POST /api/chat/stream` with a valid `widget_context` body passes the dict
   to `ChatService.stream_message`.

### Frontend (`cd frontend && npm test`)
New file `frontend/src/composables/useWidgetContext.test.ts`:
1. Returns `null` when `activeModule` is `null`.
2. Returns correct `active_panel: 'map'` and map sub-object when map panel is
   active.
3. Returns correct `active_panel: 'graph'` and graph sub-object with title and
   type of first graph.
4. Returns correct `active_panel: 'notes'` and notes sub-object with title and
   mode flag.
5. `point_count` reflects `mapStore.points.length` correctly.

---

## Acceptance Criteria
1. When the Map panel is open at zoom 8 with 2 placed pins and the user sends
   a message, the agent's system prompt contains a block mentioning "city-area
   view", "zoom level: 8", and "2 map pin(s)".
2. When the Graph panel is open with a bar chart titled "Revenue 2026" and the
   user sends a message, the system prompt contains "bar" and "Revenue 2026".
3. When the Notes panel is open with note title "Ideas" in note-taking mode and
   the user sends a message, the system prompt contains "Ideas" and the
   note-taking mode sentence.
4. When no panel is open, the system prompt is identical to today's behaviour.
5. `widget_context` absent or `null` in the request body is handled gracefully
   (no error, no change to agent behaviour).
6. All new and existing backend and frontend tests pass.

---

## Phase 2 Considerations
- **Map coordinates**: after getting explicit user consent or confirming
  regulatory compliance, include the current map center lat/lng so the agent can
  fetch location-specific data (weather, Wikipedia, etc.).
- **Active graph data**: pass a sampled subset of graph series data so the agent
  can describe trends quantitatively, not just structurally.
- **Multi-panel context**: when multiple panels are open simultaneously (Phase 2
  layout), include all open panel states in `widget_context` as an array.
- **Agent-initiated map actions**: after implementing the `map_action` Strands
  `@tool`, the agent can respond to widget context by flying to a location or
  placing a pin, closing the loop from context → response → action.
- **Streaming context updates**: push widget state changes to the backend via
  WebSocket so the agent can reference a context that changes mid-session
  (e.g., the user pans the map while the agent is still generating a response).
