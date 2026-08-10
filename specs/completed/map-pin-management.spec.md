# Spec: Map Pin Management — Edit Coordinates + Agent Pin Tools

## Purpose
Extend the map pin system in three directions:
1. **User drag-to-reposition / coordinate edit** — let the user drag an existing
   pin to a new location or type exact coordinates in the edit popup.
2. **Name at creation** — when the user right-clicks to add a pin, the creation
   popup includes a name field so the pin gets a meaningful label immediately
   instead of the default "Point N" auto-label. Leaving the field blank still
   creates the pin with the auto-label.
3. **Agent `place_pin` tool** — let the agent drop a named pin at any location
   by name or coordinates ("mark the Eiffel Tower", "pin my three offices").
3. **Agent `describe_pins` tool** — let the agent read all user-placed pins and
   describe each location (country, region, nearest city) using Nominatim
   reverse geocoding, so "What are these coordinates?" returns rich context.

## Problem Statement
The pin system from `specs/completed/map-coordinate-points.spec.md` lets users
place and label pins by right-clicking the map. Three gaps remain:
- Repositioning requires deleting and re-adding a pin; there is no drag or
  coordinate edit.
- The agent can navigate the map (`fly_to_location`) but cannot place or read
  pins — it has no way to mark a location it discovers or answer questions about
  existing pins.
- "What is at this coordinate?" requires the user to manually read a lat/lng and
  ask; the agent cannot look up pins on behalf of the user.

## Goals
1. Allow the user to **edit a pin's coordinates** by typing lat/lng into the
   existing edit popup (alongside the existing label field).
2. Allow the user to **drag a pin** to reposition it; the store is updated on
   drag-end.
3. Add agent tool `place_pin(place, label)` — geocodes the place (or accepts
   raw coordinates), adds a pin to `mapStore`, and emits a `map_action`
   artifact of type `"add_pin"` that `MapPanel.vue` renders.
4. Add agent tool `describe_pins()` — reads all pins from the chat request's
   `widget_context` (or is given them via `place_pins_json`), reverse-geocodes
   each coordinate via Nominatim, and returns a human-readable description of
   every pin (label, location description).
5. Nominatim reverse-geocoding honours the same `NOMINATIM_VERIFY_SSL` env var
   as the existing `fly_to_location` tool.

## Non-Goals
- No persistent pin storage across page reload (still session-only; see
  Phase 2 considerations).
- No bulk-import of pins from GeoJSON or CSV.
- No agent-initiated pin deletion.
- No pin clustering or category filters.
- No paid geocoder for reverse geocoding.

## User Stories
- As a user, I right-click the map, type a name in the popup, and click
  "Add pin" — the pin appears with my label immediately.
- As a user, leaving the name field blank still creates the pin with the
  default "Point N" auto-label.
- As a user, I can open a pin's edit popup, change the lat/lng fields, and the
  pin moves to the new coordinates immediately.
- As a user, I can drag a pin to a new position and its coordinates update.
- As a user, I ask "Mark the location of the Burj Khalifa" and the agent places
  a labeled pin there.
- As a user, I ask "What country are my pins in?" and the agent reverse-geocodes
  each pin and tells me.
- As a user, I ask "Tell me about Pin 2" and the agent describes the country,
  region, and nearest city for that pin's coordinates.

---

## Architecture

### Data model change (`mapStore.ts`)
`MapPoint` gains no new fields — coordinates are already `lat` / `lng`. The
`updatePointCoords(id, lat, lng)` action is added.

```typescript
function updatePointCoords(id: string, lat: number, lng: number) {
  points.value = points.value.map((p) =>
    p.id === id ? { ...p, lat, lng } : p
  )
}
```

### `add_pin` artifact shape
```json
{
  "type": "map_action",
  "action": "add_pin",
  "lat": 48.8584,
  "lng": 2.2945,
  "label": "Eiffel Tower"
}
```
`MapPanel.vue` already watches `chatStore.pendingMapAction`; extend it to handle
`action === "add_pin"` by calling `mapStore.addPoint(lat, lng)` and then
`mapStore.updatePointLabel(id, label)`.

### Reverse geocoding
Nominatim endpoint: `GET https://nominatim.openstreetmap.org/reverse?lat=...&lon=...&format=json`
Returns `address` object with `country`, `state`, `city`/`town`/`village`,
`road` etc. The agent formats these into a readable sentence per pin.

### Component map
| File | Change |
|---|---|
| `frontend/src/stores/mapStore.ts` | Add `updatePointCoords` action |
| `frontend/src/components/MapPanel.vue` | Coord fields in edit popup; draggable markers; handle `add_pin` action |
| `backend/services/strands_tools.py` | Add `build_place_pin_tool` and `build_describe_pins_tool` |
| `backend/services/chat_service.py` | Register both new tools |
| `backend/tests/test_strands_tools.py` | Tests for both new tools |
| `frontend/src/stores/mapStore.test.ts` | Tests for `updatePointCoords` |
| `frontend/src/components/MapPanel.test.ts` | Test `add_pin` action renders a marker |

---

## Frontend Requirements

### `mapStore.ts` — `updatePointCoords`
```typescript
function updatePointCoords(id: string, lat: number, lng: number) {
  points.value = points.value.map((p) =>
    p.id === id ? { ...p, lat, lng } : p
  )
}
```
Export alongside existing actions.

### `MapPanel.vue` — name-at-creation in the context-menu popup
Replace the existing single "Add point here" button with a small inline form:
```html
<div style="min-width:200px;padding:4px">
  <input id="pin-name-input" type="text" placeholder="Pin name (optional)"
    style="width:100%;border:1px solid #ccc;border-radius:4px;padding:4px;
           box-sizing:border-box;margin-bottom:6px"/>
  <button id="pin-add-btn"
    style="width:100%;background:#3b82f6;color:#fff;border:none;
           border-radius:4px;padding:4px 8px;cursor:pointer">Add pin</button>
</div>
```
On "Add pin" click (or Enter key in the name input):
1. Read the name input value. If non-empty use it as the label; otherwise
   the default `mapStore.addPoint` auto-label (`"Point N"`) is kept.
2. `const point = mapStore.addPoint(e.latlng.lat, e.latlng.lng)`
3. If a name was typed: `mapStore.updatePointLabel(point.id, typedName)`
4. `placeMarker(L, { ...point, label: typedName || point.label })`
5. Close the popup.

### `MapPanel.vue` — coordinate edit in popup
Extend the existing left-click "edit label" popup to include two additional
`<input type="number">` fields (`Latitude` / `Longitude`) pre-filled with
`point.lat` / `point.lng`. On Save:
1. If lat/lng fields differ from current, call `mapStore.updatePointCoords(id, lat, lng)`.
2. Call existing `mapStore.updatePointLabel(id, label)` for the label.
3. Move the Leaflet marker: `marker.setLatLng([newLat, newLng])`.

Validation: lat must be −90..90, lng must be −180..180; show an inline error
message in the popup if out of range (do not call store or move marker).

### `MapPanel.vue` — draggable markers
When creating a `L.marker`, pass `{ draggable: true }` as options.
On `dragend` event:
```typescript
marker.on('dragend', () => {
  const pos = marker.getLatLng()
  mapStore.updatePointCoords(point.id, pos.lat, pos.lng)
  marker.setTooltipContent(
    mapStore.points.find(p => p.id === point.id)?.label ?? point.label
  )
})
```

### `MapPanel.vue` — handle `add_pin` action
Extend the `watch(chatStore.pendingMapAction)` block:
```typescript
if (action.action === 'add_pin') {
  const point = mapStore.addPoint(action.lat, action.lng)
  mapStore.updatePointLabel(point.id, action.label)
  placeMarker(L, { ...point, label: action.label })
  map?.flyTo([action.lat, action.lng], action.zoom ?? 12)
  mapStore.setView([action.lat, action.lng], action.zoom ?? 12)
  chatStore.clearPendingMapAction()
  if (navStore.activeModule !== 'map') navStore.selectModule('map')
  return
}
```
Also update `MapAction` in `chatStore.ts` to allow `action: 'fly_to' | 'add_pin'`
and add optional `label?: string` and `zoom?: number` fields.

---

## Backend Requirements

### `build_place_pin_tool(artifact_store)`

```python
def place_pin(place: str, label: str = "") -> str:
    """Place a named pin on the map at a location.

    Use this when the user asks to mark, pin, save, or annotate a specific
    location on the map. The pin will appear immediately in the Map panel.

    place: place name or "lat, lng" coordinate string.
    label: optional label for the pin. Defaults to the resolved place name.

    After calling this tool respond with a confirmation such as
    "I've placed a pin at [label]. Would you like more information about
    this location?"
    """
    # 1. Resolve place → lat, lng (reuse _COORD_RE + Nominatim logic from fly_to)
    # 2. Determine label: use caller-supplied label if non-empty, else resolved name
    # 3. Append artifact:
    artifact_store.append({
        "type": "map_action",
        "action": "add_pin",
        "lat": lat,
        "lng": lng,
        "zoom": _zoom_for_type(osm_type),
        "label": label[:100] or resolved[:100],
    })
    return f"Pin '{effective_label}' placed at ({lat}, {lng})."
```

### `build_describe_pins_tool()`
This tool receives the pin list from the chat request via a JSON argument
(the agent is instructed to pass `widget_context.map.pins_json` when available):

```python
def describe_pins(pins_json: str) -> str:
    """Describe the geographic context of one or more map pins.

    Use this when the user asks about their pins, wants to know what country
    or region a pin is in, or asks for information about a coordinate they
    have placed on the map.

    pins_json: JSON array of pin objects from the user's map, e.g.:
      [{"id": "...", "label": "Point 1", "lat": 51.5, "lng": -0.1}]
    Pass the user's current pins from the widget context map data.
    Each pin is reverse-geocoded and described with country, region, city.
    """
    # 1. Parse pins_json → list of {id, label, lat, lng}
    # 2. For each pin, call Nominatim /reverse?lat=..&lon=..&format=json
    # 3. Build description: "Point 1 (51.5, -0.1): City of London, England, UK"
    # 4. Return joined descriptions
```

Key details:
- `pins_json` is validated as JSON; non-JSON input returns an error string.
- Each individual reverse-geocode call uses `_NOMINATIM_VERIFY_SSL` and
  `_NOMINATIM_TIMEOUT` (reusing existing constants).
- If a single pin's reverse-geocode fails, that pin gets "location unknown"
  rather than aborting the whole list.
- Maximum 20 pins processed per call to avoid rate-limit issues.

### `widget_context` extension (`widget-context-injection.spec.md`)
The map sub-object in `widget_context` gains a `pins_json` field (a JSON string
of the current `mapStore.points` array — label + lat + lng only, no internal
IDs) so the agent can pass it directly to `describe_pins` without the user
having to enumerate them:

```typescript
ctx.map = {
  zoom: mapStore.lastZoom,
  center_lat: ...,
  center_lng: ...,
  point_count: mapStore.points.length,
  pins_json: JSON.stringify(
    mapStore.points.map(p => ({ label: p.label, lat: p.lat, lng: p.lng }))
  ),
}
```

---

## Security / Validation
- Coordinate edit inputs validated client-side (lat −90..90, lng −180..180)
  before any store/marker update.
- `place` and `label` in `place_pin` capped at 500 and 100 characters
  respectively.
- `pins_json` in `describe_pins` capped at 8 KB before parsing.
- Nominatim `display_name` and `address` values rendered as text, never HTML.
- No user pin data is sent to any third party except Nominatim
  (coordinate → place name only, no label/user content).

---

## Testing Requirements

### Backend (`cd backend && python -m pytest tests/ -v`)
New tests in `test_strands_tools.py`:
1. `place_pin` with a place name calls Nominatim and emits an `add_pin` artifact.
2. `place_pin` with a coordinate string bypasses Nominatim.
3. `place_pin` uses caller-supplied label when non-empty.
4. `place_pin` falls back to resolved place name when label is empty.
5. `describe_pins` with valid JSON calls Nominatim `/reverse` for each pin.
6. `describe_pins` returns descriptive text containing country/city names.
7. `describe_pins` returns error string for invalid JSON.
8. `describe_pins` caps processing at 20 pins.
9. Individual reverse-geocode failure returns "location unknown" for that pin
   without aborting the rest.

### Frontend (`cd frontend && npm test`)
New tests in `mapStore.test.ts`:
1. `updatePointCoords` changes lat/lng of the correct pin.
2. `updatePointCoords` leaves other pins unchanged.

New tests in `MapPanel.test.ts`:
3. `add_pin` action in `chatStore.pendingMapAction` calls `L.marker` and
   `map.flyTo` with the correct coordinates.
4. Name field in the creation popup: when a non-empty name is provided,
   the resulting marker uses that label (verify via `mapStore.points[0].label`).

---

## Acceptance Criteria
1. User right-clicks the map, types "My office" in the name field, clicks
   "Add pin" — the pin labelled "My office" appears immediately with no
   second edit step required.
2. User right-clicks, leaves the name field blank — pin is created with the
   auto-label "Point N".
3. User opens a pin popup, changes the lat field, clicks Save — the pin moves
   to the new coordinate on the map and `mapStore` is updated.
2. User drags a pin — on `dragend` the `mapStore` lat/lng updates.
3. Agent tool `place_pin("Burj Khalifa")` places a pin at approximately
   (25.197, 55.274) with label "Burj Khalifa" visible in the Map panel.
4. Agent tool `describe_pins(pins_json)` returns a description naming the
   country and region for each pin.
5. "What are my pins?" in chat — the agent calls `describe_pins` with the
   current pins from widget context and returns a readable answer.
6. Invalid lat/lng in the coordinate edit popup shows a validation error and
   does not move the pin.
7. All new and existing backend and frontend tests pass.

---

## Phase 2 Considerations
- **Persistent pin storage** — save pins to the backend (`/api/map/points`)
  per-user, mirroring the notes API, so pins survive page reload.
- **Pin categories / colours** — distinguish between agent-placed and
  user-placed pins visually.
- **Batch place_pin** — accept a JSON array of `{place, label}` objects so the
  agent can place multiple pins in one tool call.
- **Pin export** — download all pins as GeoJSON for use in other tools.
- **Agent pin deletion** — `remove_pin(label)` tool that removes a named pin.
