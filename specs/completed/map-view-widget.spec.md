# Spec: Map View Widget

## Purpose
Add a "Map" widget/tab to the app header that opens an interactive world map panel, letting users pan, zoom, and explore locations on Earth independent of the chat/agent flow.

## Problem Statement
The app currently only exposes chat-centric panels toggled from the header (Graph, Notes, History, Config — see `frontend/src/App.vue`). There is no way to visually explore geographic locations. Users who want a quick, self-contained map to look around the globe have no in-app option today.

## Goals
- Add a new header toggle button ("tab") that opens a Map panel, following the existing panel-toggle pattern used by Graph/Notes/History panels.
- Provide a fully interactive world map: pan (drag), zoom in/out (scroll, +/- controls, pinch on touch), and a "reset view" control.
- Default to a reasonable world view on first open (e.g., centered at [20, 0], low zoom).
- Persist the last viewed map position/zoom for the session (in-memory store state), so reopening the panel during the same session keeps the last location.

## Non-Goals
- No search/geocoding (address or place-name lookup) in this initial version.
- No pins/markers, saved locations, or agent integration (e.g., agent asking to show a location) in this version — see Phase 2 Considerations.
- No offline map tile caching.
- No 3D globe rendering.

## User Stories
- As a user, I can click a map icon in the header to open a Map panel.
- As a user, I can drag to pan around the map and use scroll/buttons/pinch to zoom in and out.
- As a user, I can reset the map back to the default world view.
- As a user, I can close the Map panel and reopen it later in the same session without losing my last position.

## Architecture
- Frontend-only feature; no backend/API changes required since map tiles are fetched directly from a public tile provider (OpenStreetMap) by the browser.
- New Vue component `frontend/src/components/MapPanel.vue`, added to `frontend/src/App.vue` alongside the existing `GraphPanel`, `NotesPanel`, `HistoryPanel`, `ConfigPanel` panels, using the same `v-if="showMapPanel"` / header-button toggle pattern.
- New dependency: `leaflet` (MIT licensed, no API key required, uses OpenStreetMap raster tiles by default) added to `frontend/package.json`.
- New lightweight Pinia store `frontend/src/stores/mapStore.ts` to hold panel visibility and last-known center/zoom for the session (mirrors patterns in `frontend/src/stores/notesStore.ts`).

## Functional Requirements
1. Header (in `App.vue`) must include a new icon button (e.g., globe/map-pin icon) with `aria-label="Toggle map panel"` and `title="Map"`, positioned with the other panel toggle buttons.
2. Clicking the button toggles a `showMapPanel` boolean, opening/closing an `<aside>` containing `MapPanel.vue`, matching the width/layout conventions of the other side panels (e.g., `w-96` or resizable, consistent with `GraphPanel`).
3. `MapPanel.vue` must render an interactive Leaflet map that fills its container.
4. Map must support:
   - Panning via mouse drag / touch drag.
   - Zooming via scroll wheel, `+`/`-` on-map buttons, and touch pinch gestures.
   - A "Reset view" control that returns to the default center/zoom.
5. On first mount in a session, map opens at a default center (`[20, 0]`) and zoom level (`2`).
6. On subsequent opens in the same session, map restores the last center/zoom the user navigated to (stored in `mapStore`), updated on Leaflet `moveend`/`zoomend` events.
7. Only one map instance/tile-layer is initialized per panel mount; the map must be properly destroyed (`map.remove()`) on component unmount to avoid memory leaks/duplicate instances when the panel is toggled repeatedly.
8. Map panel must not attempt to render (and Leaflet must not initialize) while `v-if="showMapPanel"` is false, to avoid sizing issues with hidden containers.

## Frontend Requirements
1. Add `leaflet` and `@types/leaflet` to `frontend/package.json` dependencies/devDependencies; import Leaflet's CSS (`leaflet/dist/leaflet.css`) in `MapPanel.vue` or `main.ts`.
2. Create `frontend/src/stores/mapStore.ts`:
   - State: `showMapPanel: boolean`, `lastCenter: [number, number]`, `lastZoom: number`.
   - Actions: `toggleMapPanel()`, `setView(center, zoom)`.
3. Create `frontend/src/components/MapPanel.vue`:
   - Template: header row with panel title ("Map") and a close button (matching `NotesPanel`/`GraphPanel` conventions), plus a full-height map container `div`.
   - On `onMounted`, initialize `L.map(...)` with an OpenStreetMap `L.tileLayer` (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`) and required attribution control.
   - Attach `moveend`/`zoomend` listeners to persist `center`/`zoom` into `mapStore`.
   - On `onBeforeUnmount`, call `map.remove()` and clear the reference.
4. Update `frontend/src/App.vue`:
   - Add header button + icon for map toggle, following the existing button markup style used for Graph/Notes/History.
   - Add `<aside v-if="showMapPanel">` wrapping `MapPanel.vue`, using `mapStore.showMapPanel` (or local ref delegating to the store) consistent with how `showNotesPanel`/`showGraphPanel` are wired today.
   - Ensure only one of the right-side panels needs to be considered for width/layout consistency (existing panels already coexist independently; no mutual exclusivity requirement is being introduced).
5. Ensure Tailwind styling matches app's dark/light theme (`app-surface`, `app-border`, `app-text` classes) used elsewhere, so the Map panel header/chrome respects the existing theme toggle (see `specs/completed/dark-mode-theme-toggle.spec.md`).

## Backend Requirements
- None. No new routes, services, or config keys are required since map tiles are loaded client-side directly from the OpenStreetMap public tile server, and no location search/geocoding backend calls are in scope.

## Security/Validation
- No user-provided input is sent to any map/geocoding API in this version (no search box), so there is no injection surface from user input into a map query.
- Loading third-party tile images (OpenStreetMap) is read-only image content; no credentials or secrets are involved and none should be added to `backend/config.py`.
- Respect OpenStreetMap's tile usage policy via the standard attribution control (required by their terms) rendered on the map.

## Performance Requirements
- Leaflet map must only be instantiated when the panel is opened (lazy init on mount), not eagerly on app load.
- Map instance must be disposed on panel close/unmount to prevent leaked event listeners or duplicate tile layers.

## Accessibility Requirements
- Toggle button must have `aria-label` and `title` attributes, consistent with other header buttons.
- Zoom in/out controls must be reachable via keyboard (Leaflet's default zoom control supports keyboard focus/Enter).
- Panel close button must be keyboard-operable and labeled.

## Edge Cases
1. Panel opened/closed rapidly (toggle spam): map must not throw errors or create duplicate instances; guard init/teardown with a mounted flag or by relying on Vue's mount/unmount lifecycle per `v-if` toggle.
2. Container resized (e.g., other panel opened alongside, changing available width): call `map.invalidateSize()` on relevant resize events so tiles render correctly without gaps.
3. Tile provider network failure: map should still render (blank/gray tiles) without crashing the app; no unhandled promise rejections.
4. Very fast zoom/pan (moveend firing frequently): store updates should not cause perceptible UI lag (simple state assignment is sufficient; no debouncing required at this scale).

## Testing Requirements
- **Frontend (`cd frontend && npm test`)**:
  - `mapStore` unit tests: default state, `toggleMapPanel()` flips visibility, `setView()` updates `lastCenter`/`lastZoom`.
  - `MapPanel.vue` component test: renders map container when mounted; calls Leaflet init (mock `leaflet` module); calls `map.remove()` on unmount.
  - `App.vue` test/update: verify the map toggle button exists and toggles panel visibility (mirroring existing tests for other panel toggles, if present).

## Acceptance Criteria
1. A new header button opens/closes a Map panel without affecting other panels' behavior.
2. The Map panel renders an interactive world map that supports pan and zoom (mouse, buttons, and touch).
3. Reopening the Map panel within the same session restores the last center/zoom.
4. No console errors/memory leaks occur when toggling the panel open/closed repeatedly.
5. Existing chat, graph, notes, history, and config functionality remain unaffected (no regressions).
6. All new/updated frontend tests pass via `cd frontend && npm test`.

## Phase 2 Considerations
- Location search/geocoding (place name → coordinates) with a search box.
- Ability for the agent to instruct the map to fly to a specific location based on chat context (e.g., "show me Tokyo").
- Saved/favorite locations or markers, persisted per user (would require backend storage, similar to `chat-history-side-panel.spec.md` patterns).
- Support for alternate map tile styles (satellite, terrain) or a paid provider requiring an API key (would need to follow the environment-only secret handling convention in `backend/config.py`).
