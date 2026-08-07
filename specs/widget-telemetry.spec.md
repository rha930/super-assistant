# Spec: Widget Telemetry — User Activity Tracking

## Purpose
Capture lightweight, privacy-conscious telemetry events when users interact
with the AERIAL widgets (Map, Graph, Notes, Chat History) so the development
team can understand which features are used, how often, and in what sequences —
without collecting message content, personal identifiers beyond a session token,
or any data that requires user consent under GDPR/CCPA.

## Problem Statement
The app has no signal on which panels users open, how long they stay, or which
widget actions (pan/zoom on the map, graph clicks, note saves) are actually
used. Without this signal it is impossible to prioritise Phase 2 features, spot
usability regressions, or understand whether new widgets are adopted. A
server-side event log using only structural metadata (event type, panel name,
duration, session token) provides the necessary insight with minimal privacy
risk.

## Goals
1. Define a small, stable set of telemetry event types covering the key widget
   interactions (panel open/close, session duration, map view-change, graph
   render, note save, history load).
2. Emit events from the frontend via a lightweight fire-and-forget API call to a
   new `/api/telemetry/event` backend endpoint.
3. Store events server-side in an append-only SQLite table (reusing the existing
   local storage pattern from `history_repository_local.py`).
4. Never collect message content, note content, LLM responses, map coordinates,
   or any PII. The session token is a random UUID generated on app load with no
   link to the authenticated user's identity.
5. Telemetry emission is opt-out via a `TELEMETRY_ENABLED` env var defaulting
   to `True`; when disabled, the frontend silently drops events and the endpoint
   returns 200 without writing.
6. Telemetry failures (network error, backend down) must never surface errors to
   the user or break any widget.

## Non-Goals
- No real-time dashboard or analytics UI in this version.
- No third-party analytics service (no Segment, Mixpanel, PostHog, etc.).
- No user-level attribution — session token is ephemeral and not linked to
  `user_id`.
- No telemetry on chat message content, note content, or LLM output.
- No A/B testing or feature flags.
- No retention policy enforcement in this version (raw table, no auto-purge).

## User Stories
- As a developer, I can query the SQLite telemetry table to see which panels are
  opened most frequently.
- As a developer, I can see average panel session duration to identify panels
  users abandon quickly.
- As a developer, I can see how often map zoom/pan events fire to know if the
  map is actively used after opening.
- As a user, I am not asked for consent because no PII or content is collected;
  I can opt out by setting `TELEMETRY_ENABLED=False` in the environment.

## Architecture

### Event schema (all events)
```json
{
  "session_id": "uuid-v4 (ephemeral, generated in frontend on app load)",
  "event_type": "string (see Event Types below)",
  "widget": "string | null  (map | graph | notes | history | chat | config)",
  "metadata": { /* event-type-specific, structural only, no content */ },
  "client_ts": "ISO 8601 timestamp from browser"
}
```

### Event types
| `event_type` | `widget` | `metadata` |
|---|---|---|
| `panel_opened` | panel name | `{}` |
| `panel_closed` | panel name | `{ "duration_ms": number }` |
| `map_view_changed` | `"map"` | `{ "zoom": number }` (no coordinates) |
| `map_point_added` | `"map"` | `{ "total_points": number }` |
| `map_point_deleted` | `"map"` | `{ "total_points": number }` |
| `graph_rendered` | `"graph"` | `{ "chart_type": "line\|bar\|pie" }` |
| `note_saved` | `"notes"` | `{}` |
| `history_conversation_loaded` | `"history"` | `{}` |
| `agent_message_sent` | `"chat"` | `{ "provider": "ollama\|gemini" }` |

### Data flow
```
Frontend widget event
  → useTelemetry() composable (fire-and-forget fetch)
    → POST /api/telemetry/event
      → TelemetryService.record(event)
        → SQLite: telemetry_events table
```

### Component map
| File | Change |
|---|---|
| `frontend/src/composables/useTelemetry.ts` | **New** — composable exposing `track(event_type, widget?, metadata?)` |
| `frontend/src/main.ts` | Generate `session_id` on app load, store in `useTelemetryStore` |
| `frontend/src/stores/telemetryStore.ts` | **New** — holds `session_id`, wraps `track()` calls |
| `frontend/src/components/MapPanel.vue` | Emit `panel_opened`, `panel_closed`, `map_view_changed`, `map_point_added`, `map_point_deleted` |
| `frontend/src/components/NavBar.vue` | Emit `panel_opened` / `panel_closed` on module switch |
| `frontend/src/components/NotesPanel.vue` | Emit `note_saved` from Save action |
| `frontend/src/components/HistoryPanel.vue` | Emit `history_conversation_loaded` on conversation select |
| `frontend/src/App.vue` | Emit `panel_opened` / `panel_closed` for History and Config |
| `backend/services/telemetry_service.py` | **New** — SQLite writer, no-op when disabled |
| `backend/routes/telemetry.py` | **New** — `POST /api/telemetry/event` |
| `backend/app.py` | Register `telemetry_bp` |
| `backend/config.py` | Add `TELEMETRY_ENABLED`, `TELEMETRY_DB_PATH` |

---

## Backend Requirements

### `backend/config.py`
Add:
```python
TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "True") == "True"
TELEMETRY_DB_PATH = os.getenv("TELEMETRY_DB_PATH", "./backend/data/telemetry.db")
```

### `backend/services/telemetry_service.py`
- Class `TelemetryService` with `__init__(enabled: bool, db_path: str)`.
- On init: create SQLite DB + `telemetry_events` table if it does not exist:
  ```sql
  CREATE TABLE IF NOT EXISTS telemetry_events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    widget     TEXT,
    metadata   TEXT,       -- JSON string
    client_ts  TEXT,
    server_ts  TEXT NOT NULL  -- server-side UTC ISO 8601
  )
  ```
- `record(event: dict) -> None`:
  - If `enabled` is `False`, return immediately (no-op).
  - Validate required fields (`session_id`, `event_type`) are non-empty strings;
    silently drop malformed events (never raise to caller).
  - Strip any fields outside the schema before writing.
  - Insert one row; never raise — catch all exceptions and log at WARNING level.
- No read methods in this version (no query API).

### `backend/routes/telemetry.py`
- `POST /api/telemetry/event` — no auth required (session_id is anonymous).
- Accept JSON body matching the event schema.
- Call `telemetry_service.record(data)`.
- Always return `{"success": true}` with HTTP 200 (even on validation failure or
  when telemetry is disabled) to ensure frontend fire-and-forget never retries.
- Reject requests with body > 4 KB (return 413) to prevent abuse.

### `backend/app.py`
Register `telemetry_bp` alongside existing blueprints.

---

## Frontend Requirements

### `frontend/src/stores/telemetryStore.ts` (new)
```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTelemetryStore = defineStore('telemetry', () => {
  // Ephemeral random session id — no link to authenticated user
  const sessionId = ref(crypto.randomUUID())
  return { sessionId }
})
```

### `frontend/src/composables/useTelemetry.ts` (new)
```typescript
export function useTelemetry() {
  const store = useTelemetryStore()

  function track(
    event_type: string,
    widget?: string,
    metadata?: Record<string, unknown>
  ): void {
    if (!TELEMETRY_ENABLED) return  // env var injected by Vite
    const payload = {
      session_id: store.sessionId,
      event_type,
      widget: widget ?? null,
      metadata: metadata ?? {},
      client_ts: new Date().toISOString(),
    }
    // Fire-and-forget: never await, never surface errors
    fetch('/api/telemetry/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }).catch(() => {/* swallow — telemetry must never break the UI */})
  }

  return { track }
}
```

`TELEMETRY_ENABLED` is a `import.meta.env.VITE_TELEMETRY_ENABLED` boolean
(default `true`); add `VITE_TELEMETRY_ENABLED=false` to disable.

### Panel instrumentation
Each `track()` call is a one-liner added to existing lifecycle hooks or event
handlers — no restructuring of component logic:

**MapPanel.vue**
- `onMounted` (after map init): `track('panel_opened', 'map')`
- `onBeforeUnmount`: `track('panel_closed', 'map', { duration_ms })`
- `moveend`/`zoomend` handler: `track('map_view_changed', 'map', { zoom })`
  — coordinates are NOT included.
- After `mapStore.addPoint(...)` succeeds: `track('map_point_added', 'map', { total_points: mapStore.points.length })`
- After `mapStore.removePoint(...)` succeeds: `track('map_point_deleted', 'map', { total_points: mapStore.points.length })`

**NavBar.vue**
- `selectModule` click: `track('panel_opened', module)` when opening;
  `track('panel_closed', prev_module, { duration_ms })` when closing/switching.

**NotesPanel.vue**
- `saveNote` call: `track('note_saved', 'notes')`.

**HistoryPanel.vue**
- Conversation `click` handler: `track('history_conversation_loaded', 'history')`.

**App.vue**
- History toggle: `track('panel_opened'/'panel_closed', 'history', { duration_ms? })`.

**ChatWindow.vue** (or route handler)
- On stream start: `track('agent_message_sent', 'chat', { provider })`.

### `docker-compose.yml`
Add `VITE_TELEMETRY_ENABLED` to the frontend service's environment block
(default unset = enabled). Add `TELEMETRY_ENABLED` and `TELEMETRY_DB_PATH` to
the backend environment block.

---

## Security / Validation
- No authentication on `POST /api/telemetry/event` — but body size is capped at
  4 KB server-side to prevent abuse.
- `session_id` is a random UUID with no link to the authenticated `user_id`;
  the backend never joins telemetry data with user records.
- `metadata` values are stored as a JSON string; content is never evaluated or
  echoed back in any response.
- Map coordinates, note content, message content, and LLM responses are
  explicitly excluded from all event payloads (enforced by schema strip in
  `TelemetryService.record`).
- Telemetry DB is a separate file (`telemetry.db`) from the chat history DB to
  keep concerns isolated.

---

## Testing Requirements

### Backend (`cd backend && python -m pytest tests/ -v`)
New file `backend/tests/test_telemetry_service.py`:
1. `record()` inserts a row into the DB when enabled.
2. `record()` is a no-op (no row inserted) when `enabled=False`.
3. `record()` silently drops events with missing `session_id`.
4. `record()` silently drops events with missing `event_type`.
5. `POST /api/telemetry/event` returns `{"success": true}` for a valid payload.
6. `POST /api/telemetry/event` returns `{"success": true}` even for a malformed
   payload (telemetry errors must not surface).
7. `POST /api/telemetry/event` returns 413 for a body > 4 KB.

### Frontend (`cd frontend && npm test`)
New file `frontend/src/composables/useTelemetry.test.ts`:
1. `track()` calls `fetch` with the correct endpoint and payload shape.
2. `track()` includes `session_id` from `telemetryStore`.
3. `track()` does not throw when `fetch` rejects.
4. `track()` is a no-op when `VITE_TELEMETRY_ENABLED` is `false`.

New file `frontend/src/stores/telemetryStore.test.ts`:
5. `sessionId` is a non-empty string on store creation.
6. `sessionId` is stable within a store instance (does not regenerate on access).

---

## Acceptance Criteria
1. Every widget panel open/close emits `panel_opened` / `panel_closed` events
   visible in the telemetry SQLite DB.
2. Map zoom-level changes emit `map_view_changed` with zoom but no coordinates.
4. Map point additions and deletions emit `map_point_added` / `map_point_deleted` with the running `total_points` count but no coordinates or labels.
5. Note saves, history loads, and agent messages each emit their respective
   events.
4. Telemetry failures (backend unreachable) produce no visible error in the UI.
5. Setting `TELEMETRY_ENABLED=False` (backend) or `VITE_TELEMETRY_ENABLED=false`
   (frontend) disables all event recording.
6. All backend and frontend tests pass.
7. No user PII, message content, or map coordinates appear in the telemetry DB.

---

## Phase 2 Considerations
- **Retention policy**: auto-purge events older than N days via a background
  task or cron job.
- **Admin dashboard**: a read-only `/api/telemetry/summary` endpoint returning
  aggregate counts per event type / widget for display in the Config panel.
- **Funnel analysis**: sequence events by `session_id` to identify drop-off
  points (e.g., users who open Graph but never interact with it).
- **Error telemetry**: capture frontend JS errors (unhandled exceptions) as a
  separate event type to track regressions in production.
- **Map-point events**: ~~wire `map_point_added` / `map_point_deleted` once the
  map-coordinate-points spec is implemented~~ (now implemented — see
  `specs/completed/map-coordinate-points.spec.md`).
