# Spec: Agent Map Navigation Tool — Fly-To Location

## Purpose
Give the agent a `fly_to_location` Strands `@tool` that moves the map panel
to a specific place by name or coordinates when the user asks natural-language
questions like "Show me London", "Zoom in on the Amazon basin", or "Navigate to
48.8566, 2.3522". The map panel animates to the new view and the user sees the
result without typing a single coordinate.

## Problem Statement
The AERIAL agent can currently describe a location in text and the user can see
their current map viewport in widget context (`specs/widget-context-injection.spec.md`),
but there is no mechanism for the agent to *move* the map. Users must pan and
zoom manually to follow up on any location the agent mentions. Adding a
`fly_to_location` tool closes this loop: the agent names a place, the map
moves there.

## Goals
1. Add a `fly_to_location` Strands `@tool` to `backend/services/strands_tools.py`
   that accepts a place name (and optional zoom hint) and resolves it to
   coordinates using the Nominatim geocoding API (OpenStreetMap's public,
   free-to-use geocoder — no API key required).
2. The tool emits a **map action artifact** (JSON in the agent's response stream,
   analogous to graph artifacts) containing `{ type: "map_action", action:
   "fly_to", lat, lng, zoom }`.
3. `MapPanel.vue` watches the chat store for incoming `map_action` artifacts
   and calls `map.flyTo([lat, lng], zoom)` when one arrives.
4. `mapStore` is updated with the new center and zoom after the fly-to completes
   so widget context stays current.
5. The tool also accepts raw coordinates (`"48.8566, 2.3522"`) as a fallback
   when the place name is provided in coordinate form.
6. The Map panel is auto-opened by the nav store if it is not already active
   when a fly-to action arrives.

## Non-Goals
- No reverse geocoding ("what place is at these coordinates?") in this version.
- No multi-stop routes or animated tours — single fly-to per tool call.
- No custom marker placement from this tool — that is `map_point_added` (see
  `specs/completed/map-coordinate-points.spec.md`). The tool moves the view; it
  does not drop a pin.
- No caching of geocoding results in this version.
- No paid geocoding provider or API key — Nominatim only.
- No offline/self-hosted geocoding.

## User Stories
- As a user, I say "Show me London" and the map panel opens and flies to London.
- As a user, I say "Zoom in to street level in Shibuya" and the map moves to
  Shibuya at high zoom.
- As a user, I paste coordinates into the chat ("Navigate to 35.68, 139.69")
  and the map flies there.
- As a user, if the place can't be found, the agent tells me it couldn't locate
  it — the map doesn't move.

## Architecture

### Geocoding
- Use Nominatim (`https://nominatim.openstreetmap.org/search`) with
  `format=json&limit=1&q=<place>`.
- Set `User-Agent: AERIAL-App/1.0` in the request header (required by
  Nominatim's terms of use).
- Cache: none in this version. Rate-limit: Nominatim's free tier allows 1 req/s;
  the agent will not call this on every message, only on explicit user intent.
- Coordinate input: detect `"<float>, <float>"` pattern with a regex before
  calling Nominatim; parse directly if matched.

### Artifact shape
The tool returns a string response to the Strands SDK (required by `@tool`
return type) and *also* emits a side-channel artifact via the same
`artifact_store` list mechanism used by `generate_graph`:

```python
artifact_store.append({
    "type": "map_action",
    "action": "fly_to",
    "lat": lat,
    "lng": lng,
    "zoom": zoom,
    "place_name": resolved_name,
})
```

The string returned to the LLM: `"Flying to <resolved_name> (lat, lng) at zoom Z."`

### Frontend — artifact consumption
`ChatWindow.vue` (or the existing artifact-handling path in `chatStore`) already
forwards artifacts from stream metadata to `chatStore.currentGraphs` for graph
artifacts. This spec adds a parallel path for `type: "map_action"`:

```
Stream done event
  → finalMetadata.artifacts includes { type: "map_action", ... }
    → chatStore dispatches/stores mapActions
      → MapPanel.vue watches chatStore.pendingMapAction
        → map.flyTo([lat, lng], zoom)
        → mapStore.setView([lat, lng], zoom)
        → navStore.selectModule('map') if not already active
        → chatStore.clearPendingMapAction()
```

### Component map
| File | Change |
|---|---|
| `backend/services/strands_tools.py` | Add `build_fly_to_location_tool(artifact_store)` factory |
| `backend/services/chat_service.py` | Include `fly_to_location` tool when building the agent |
| `backend/tests/test_strands_tools.py` | New tests for `fly_to_location` tool |
| `frontend/src/stores/chatStore.ts` | Add `pendingMapAction` ref + `setPendingMapAction` / `clearPendingMapAction` |
| `frontend/src/components/MapPanel.vue` | `watch(chatStore.pendingMapAction)` → `map.flyTo` |
| `frontend/src/stores/chatStore.test.ts` | Tests for new store actions |
| `frontend/src/components/MapPanel.test.ts` | Test that `map.flyTo` is called when action arrives |

---

## Backend Requirements

### `backend/services/strands_tools.py` — new factory

```python
_COORD_RE = re.compile(
    r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)\s*$"
)
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_HEADERS = {"User-Agent": "AERIAL-App/1.0"}
_NOMINATIM_TIMEOUT = 8  # seconds

def _zoom_for_type(osm_type: str | None) -> int:
    """Return a sensible default zoom for the Nominatim place type."""
    mapping = {
        "continent": 3, "country": 5, "state": 7, "county": 9,
        "city": 10, "town": 12, "village": 13, "suburb": 14,
        "neighbourhood": 15, "building": 17,
    }
    return mapping.get(osm_type or "", 10)

def build_fly_to_location_tool(artifact_store: list):
    """Return a @tool that navigates the map to a named place or coordinates."""

    def fly_to_location(place: str, zoom: int = 0) -> str:
        """Navigate the map panel to a specific location by place name or coordinates.

        Use this when the user asks to show, navigate to, zoom in on, or
        go to a specific place on the map. The map panel will fly to the
        requested location automatically.

        place: a place name ("London", "Amazon rainforest") or decimal
               coordinates as "lat, lng" (e.g. "48.8566, 2.3522").
        zoom:  optional zoom level 1–19. If 0 or omitted the tool picks a
               sensible default based on the place type (country → 5,
               city → 10, neighbourhood → 15, etc.).
        """
        place = place.strip()[:500]
        if not place:
            return "No place specified."

        # Try direct coordinate parse first
        coord_match = _COORD_RE.match(place)
        if coord_match:
            lat = round(float(coord_match.group(1)), 6)
            lng = round(float(coord_match.group(2)), 6)
            resolved = place
            osm_type = None
        else:
            # Geocode via Nominatim
            try:
                resp = requests.get(
                    _NOMINATIM_URL,
                    params={"q": place, "format": "json", "limit": 1},
                    headers=_NOMINATIM_HEADERS,
                    timeout=_NOMINATIM_TIMEOUT,
                )
                resp.raise_for_status()
                results = resp.json()
            except Exception as exc:
                logger.warning("Nominatim geocoding failed for %r: %s", place, exc)
                return f"Could not geocode '{place}': service unavailable."

            if not results:
                return f"Could not find a location matching '{place}'."

            hit = results[0]
            lat = round(float(hit["lat"]), 6)
            lng = round(float(hit["lon"]), 6)
            resolved = hit.get("display_name", place)
            osm_type = hit.get("type") or hit.get("addresstype")

        effective_zoom = zoom if 1 <= zoom <= 19 else _zoom_for_type(osm_type)
        artifact_store.append({
            "type": "map_action",
            "action": "fly_to",
            "lat": lat,
            "lng": lng,
            "zoom": effective_zoom,
            "place_name": resolved[:200],
        })
        return (
            f"Flying to {resolved[:80]} "
            f"(lat={lat}, lng={lng}) at zoom {effective_zoom}."
        )

    return strands_tool(fly_to_location)
```

### `backend/services/chat_service.py`
Add `build_fly_to_location_tool(artifact_store)` to the `tools` list in
`_build_strands_agent`, alongside `build_news_search_tool` and
`build_generate_graph_tool`.

### Validation rules (enforced in the tool function)
- `place` is stripped and capped at 500 characters.
- `zoom` must be 1–19; any other value triggers the auto-zoom lookup.
- `lat` must be −90 to 90 and `lng` −180 to 180; out-of-range values from
  Nominatim are rejected and the tool returns an error string.
- Nominatim `display_name` is capped at 200 characters in the artifact.

---

## Frontend Requirements

### `frontend/src/stores/chatStore.ts` additions
```typescript
const pendingMapAction = ref<MapAction | null>(null)

interface MapAction {
  action: 'fly_to'
  lat: number
  lng: number
  zoom: number
  place_name: string
}

function setPendingMapAction(action: MapAction) {
  pendingMapAction.value = action
}

function clearPendingMapAction() {
  pendingMapAction.value = null
}
```

Expose `pendingMapAction`, `setPendingMapAction`, `clearPendingMapAction` from
the store.

### Artifact routing (existing `finalize_stream_message` path)
After stream completion, iterate `artifacts` and route by type:
- `type === "graph"` → existing `currentGraphs` path (unchanged)
- `type === "map_action"` → call `chatStore.setPendingMapAction(artifact)`

This routing already happens in `ChatWindow.vue` or wherever artifacts are
processed from the final SSE event.

### `frontend/src/components/MapPanel.vue` additions
```typescript
import { watch } from 'vue'
import { useChatStore } from '../stores/chatStore'
import { useNavStore } from '../stores/navStore'

const chatStore = useChatStore()
const navStore = useNavStore()

watch(
  () => chatStore.pendingMapAction,
  (action) => {
    if (!action || action.action !== 'fly_to') return
    // Auto-open the map panel if it isn't already active
    if (navStore.activeModule !== 'map') {
      navStore.selectModule('map')
    }
    // flyTo is safe to call even before the Leaflet map is mounted because
    // MapPanel mounts when navStore.activeModule === 'map' (v-if guard in App.vue).
    // The nextTick here ensures the map DOM exists after selectModule().
    nextTick(() => {
      map?.flyTo([action.lat, action.lng], action.zoom)
      mapStore.setView([action.lat, action.lng], action.zoom)
      chatStore.clearPendingMapAction()
    })
  },
)
```

---

## Security / Validation
- `place` is a user-provided string; it is passed to Nominatim as the `q` query
  parameter — it is never executed or echoed as HTML in the backend.
- The Nominatim `display_name` returned from the geocoder is stored in the
  artifact at `place_name` and later rendered as text content in the frontend
  (not innerHTML), preventing XSS.
- `lat` and `lng` from Nominatim are parsed as `float`; non-numeric responses
  cause the tool to return an error string rather than propagating an exception.
- Backend coordinate range validation: `abs(lat) > 90` or `abs(lng) > 180`
  → tool returns an error string.
- No Nominatim API key is required and none must be added to `config.py`.
- Nominatim is called with a hard timeout of 8 seconds; slow responses do not
  hang the agent.

## Accessibility
- The map fly-to animation is CSS-driven by Leaflet; no ARIA changes needed.
- The agent's text response describes the destination ("Flying to London…") so
  screen reader users know what happened without seeing the map.

---

## Testing Requirements

### Backend (`cd backend && python -m pytest tests/ -v`)
Extend `backend/tests/test_strands_tools.py`:
1. `fly_to_location` with a coordinate string (`"51.5, -0.1"`) resolves without
   calling Nominatim and emits correct lat/lng in the artifact.
2. `fly_to_location` with a valid place name calls Nominatim with the correct
   URL and query, and emits a `map_action` artifact with `action: "fly_to"`.
3. `fly_to_location` returns an error string when Nominatim returns no results.
4. `fly_to_location` returns an error string (does not raise) when Nominatim
   raises a network exception.
5. `fly_to_location` caps the place input at 500 characters.
6. `fly_to_location` uses the caller-supplied `zoom` when `1 ≤ zoom ≤ 19`.
7. `fly_to_location` auto-selects zoom from `_zoom_for_type` when `zoom=0`.
8. Out-of-range lat/lng from Nominatim is rejected with an error string.

### Frontend (`cd frontend && npm test`)
Extend `frontend/src/stores/chatStore.test.ts`:
1. `setPendingMapAction` stores the action in `pendingMapAction`.
2. `clearPendingMapAction` resets `pendingMapAction` to `null`.

Extend `frontend/src/components/MapPanel.test.ts`:
3. When `chatStore.pendingMapAction` is set to a `fly_to` action after mount,
   `map.flyTo` is called with the correct `[lat, lng]` and `zoom`.
4. After `flyTo` is called, `chatStore.clearPendingMapAction()` is called.

---

## Acceptance Criteria
1. User says "Show me London" → agent calls `fly_to_location("London")` →
   map panel opens (if closed) and animates to London (approx. 51.5, -0.1)
   at zoom ~10.
2. User says "Navigate to 35.68, 139.69" → map flies to those exact coordinates.
3. User says "Show me Xyz123Nonexistent" → agent responds with "Could not find
   a location matching…" and the map does not move.
4. Nominatim unreachable → tool returns an error string; the agent communicates
   the failure; the map does not move and no exception propagates to the user.
5. All new and existing backend and frontend tests pass.

---

## Phase 2 Considerations
- **Marker on arrival**: optionally place a pin at the destination after flying
  to it (combining with `map-coordinate-points.spec.md`).
- **Bounding-box fit**: for country/region queries, use `map.fitBounds` instead
  of `flyTo` so the whole region is visible without manual zooming.
- **Result disambiguation**: when Nominatim returns multiple results, surface
  the top 3 to the user ("Did you mean London, UK or London, Ontario?").
- **Nominatim caching**: cache geocoding results in memory (LRU, max 100 entries)
  to avoid redundant API calls when the agent references the same place in
  multiple turns.
- **Alternative providers**: add an optional env-var-configurable geocoding
  provider (Mapbox, Google) for higher rate limits and better coverage.
