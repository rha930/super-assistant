# Spec: Map Coordinate Points — User-Placed Markers

## Purpose
Let users right-click anywhere on the map to place a persistent, labeled marker
(coordinate point), and right-click an existing marker to delete it — giving
users a lightweight way to annotate geographic locations directly on the map.

## Problem Statement
The current `MapPanel.vue` renders a world map that supports pan, zoom, and
session-persistent view state, but provides no way to mark or save specific
locations. Users who want to record a coordinate, annotate a place of interest,
or hand context to the agent must type coordinates manually. A right-click
marker workflow (familiar from mapping tools like Google Maps) closes this gap
without adding a search/geocoding backend.

## Goals
1. Right-click on empty map canvas → context menu with "Add point here" option
   → places a marker pin with a default label ("Point N") at the clicked
   coordinates.
2. Right-click an existing marker → context menu with "Delete point" option →
   removes the marker.
3. All placed markers persist for the session (stored in `mapStore`); reopening
   the Map panel in the same session restores them.
4. Each marker has an editable label (click the marker → popup with label input
   + confirm button so users can rename it).
5. Markers use a distinct icon (default Leaflet pin, or a custom SVG pin that
   respects the app's accent colour) and are numbered sequentially.

## Non-Goals
- No persistence across page reload or browser sessions (localStorage /
  backend storage is a Phase 2 concern).
- No drag-to-reposition markers in this version.
- No search/geocoding ("place a marker at Paris") — that remains in Phase 2.
- No agent-triggered marker placement in this version (see Phase 2).
- No marker categories or custom colours per marker.
- No import/export of marker collections.

## User Stories
- As a user, I can right-click on the map to place a numbered pin at that spot.
- As a user, I can click a pin to see its label and rename it via a popup.
- As a user, I can right-click an existing pin to remove it.
- As a user, when I close and reopen the Map panel in the same session, all my
  pins are still there.

## Architecture

### Data model (`mapStore.ts`)
```typescript
interface MapPoint {
  id: string           // uuid
  lat: number
  lng: number
  label: string        // default "Point N" where N is a counter
}
```

`mapStore` gains:
- `points: ref<MapPoint[]>([])` — session-persisted array
- `addPoint(lat, lng) → MapPoint` — appends with auto-incremented label
- `removePoint(id: string)` — removes by id
- `updatePointLabel(id: string, label: string)` — renames
- `pointCounter: ref<number>(0)` — monotonically increasing for default labels

### Leaflet integration (`MapPanel.vue`)
- On `contextmenu` map event (right-click on canvas): show native Leaflet
  popup with an "Add point" button at the clicked latlng.
- On `contextmenu` marker event (right-click on a marker): show popup with
  "Delete point" button.
- Clicking a marker (left-click) opens a popup with a text input pre-filled
  with the marker's current label and a "Save" button.
- `watchEffect` (or `watch(mapStore.points)`) syncs the Leaflet layer with the
  store: adds/removes `L.marker` instances when the store array changes.
- Markers are stored in a `Map<string, L.Marker>` local to the component
  (keyed by point id) for O(1) lookup during removal.

### No backend changes
All data lives in the Pinia `mapStore`; no API calls or new routes are needed.

## Functional Requirements

### Adding a point
1. User right-clicks on the map canvas (not on an existing marker).
2. A Leaflet popup appears at the clicked location with an "Add point here"
   button.
3. Clicking the button:
   a. Calls `mapStore.addPoint(lat, lng)`.
   b. Closes the popup.
   c. Places a `L.marker` at the coordinates, bound with a click-to-edit popup
      and a contextmenu-to-delete popup.
4. The marker's default tooltip shows its label ("Point 1", "Point 2", …).

### Editing a label
1. User left-clicks a marker.
2. A Leaflet popup opens containing:
   - A text `<input>` pre-filled with the current label.
   - A "Save" button.
3. Clicking Save calls `mapStore.updatePointLabel(id, newLabel)` and updates
   the marker tooltip.

### Deleting a point
1. User right-clicks an existing marker.
2. A Leaflet popup opens with a "Delete point" button.
3. Clicking Delete calls `mapStore.removePoint(id)` and removes the Leaflet
   marker from the map.

### Session persistence
- On `MapPanel.vue` `onMounted`, after the Leaflet map is initialised, iterate
  `mapStore.points` and re-create `L.marker` instances for any previously saved
  points (handles panel close/reopen within the same session).

## Frontend Requirements

### `mapStore.ts` changes
Add to the existing store (do not replace existing state/actions):
```typescript
const points = ref<MapPoint[]>([])
const pointCounter = ref(0)

function addPoint(lat: number, lng: number): MapPoint {
  pointCounter.value += 1
  const point: MapPoint = {
    id: crypto.randomUUID(),
    lat,
    lng,
    label: `Point ${pointCounter.value}`,
  }
  points.value = [...points.value, point]
  return point
}

function removePoint(id: string) {
  points.value = points.value.filter(p => p.id !== id)
}

function updatePointLabel(id: string, label: string) {
  points.value = points.value.map(p => p.id === id ? { ...p, label } : p)
}
```

Export `MapPoint` type from `mapStore.ts`.

### `MapPanel.vue` changes
1. Add `const markerLayer = new Map<string, L.Marker>()` (local, not reactive).
2. After Leaflet map init, call `restorePoints()` to re-add any markers already
   in `mapStore.points`.
3. Register `map.on('contextmenu', handleMapContextMenu)`.
4. `handleMapContextMenu(e)`:
   - Opens an `L.popup` at `e.latlng` with HTML:
     `<button id="map-add-point">Add point here</button>`
   - After popup opens, attach a `click` handler to `#map-add-point` that calls
     `placeMarker(mapStore.addPoint(e.latlng.lat, e.latlng.lng))` and closes
     the popup.
5. `placeMarker(point: MapPoint)`:
   - Creates `L.marker([point.lat, point.lng])`.
   - Binds tooltip with `point.label` (permanent: false, so it shows on hover).
   - Binds a click popup (edit label form).
   - Binds a contextmenu popup (delete button).
   - Adds to `map` and stores in `markerLayer.set(point.id, marker)`.
6. `restorePoints()`: loops `mapStore.points` and calls `placeMarker` for each.
7. On `onBeforeUnmount`: clear `markerLayer` (map removal handles Leaflet
   cleanup automatically via `map.remove()`).

### No changes required to
- `NavBar.vue`, `App.vue`, `navStore.ts`, other panels.

## Security / Validation
- Label input is set via `marker.setTooltipContent()` / DOM text node — never
  set as raw `innerHTML`; no XSS surface.
- Coordinates come directly from Leaflet's `contextmenu` event `latlng` which
  are validated numbers; no user string is parsed as a coordinate.
- No data is sent to any backend in this version.

## Accessibility
- The popup "Add point here", "Save", and "Delete point" buttons must be
  reachable by keyboard once the popup is open (Leaflet popups are in the DOM
  and focusable).
- Marker tooltips provide a visible label without requiring interaction.
- Right-click as the only trigger is acceptable for MVP (touch long-press is a
  Phase 2 concern).

## Testing Requirements
**Frontend (`cd frontend && npm test`)**

`mapStore` additions (`mapStore.test.ts` — extend existing file):
1. `addPoint` appends a point with correct lat/lng and auto-label.
2. `addPoint` increments label counter across multiple calls.
3. `removePoint` removes the correct point by id and leaves others untouched.
4. `updatePointLabel` updates only the named point's label.
5. `points` starts as an empty array; `pointCounter` starts at 0.

`MapPanel.vue` additions (`MapPanel.test.ts` — extend existing file):
6. `restorePoints` is called on mount and calls `placeMarker` once per existing
   store point (mock `mapStore.points` with one entry, verify `L.marker` is
   called once in addition to the map init call).

## Acceptance Criteria
1. Right-clicking on the map opens a popup with "Add point here".
2. Clicking "Add point here" places a numbered marker at the clicked location.
3. Left-clicking a marker opens a popup with a label input; saving updates the
   tooltip.
4. Right-clicking a marker opens a popup with "Delete point"; clicking it
   removes the marker.
5. Closing and reopening the Map panel within the same session restores all
   placed markers.
6. All new and existing frontend tests pass via `cd frontend && npm test`.

## Phase 2 Considerations
- Persist markers to the backend (new `/api/map/points` routes, mirroring the
  notes API pattern) so they survive page reload and are per-user.
- Agent-triggered marker placement via a `place_marker(lat, lng, label)` Strands
  `@tool`, emitting a map artifact the MapPanel listens for (consistent with
  the `generate_graph` pattern in `strands_tools.py`).
- Send current marker collection as context to the agent on each message
  (appended to the workspace state snapshot described in the agent-map
  interaction ideas).
- Drag-to-reposition existing markers.
- Touch long-press as an alternative to right-click for mobile / trackpad users.
- Marker clustering when many points overlap at low zoom levels (Leaflet
  MarkerCluster plugin).
