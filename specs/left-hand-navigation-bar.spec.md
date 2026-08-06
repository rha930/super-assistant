# Spec: Left-Hand Navigation Bar for Widget Panels

## Purpose
Restructure the app shell so all widget/module panels (Graph, Notes, Chat History, Map) are launched from a vertical navigation bar on the left edge of the screen and open as a panel on the left, with the chat window occupying the remaining space to the right. User identity, Settings, and Log out remain in the top-right of the header.

## Problem Statement
Today, `frontend/src/App.vue` toggles Graph, Notes, History, Config, and Map panels from a single row of icon buttons in the top-right of the header, and every opened panel renders as an `<aside>` to the right of `ChatWindow` (see the `<main>` block: `ChatWindow` first, followed by `GraphPanel`/`ConfigPanel`/`HistoryPanel`/`NotesPanel`/`MapPanel` asides). As more widgets are added (e.g., the Map panel introduced in `specs/completed/map-view-widget.spec.md`, and the planned database connectors tool in `specs/database-connectors-and-query-tool.spec.md`), the header becomes crowded and there's no consistent, scalable place for module navigation. Users have also indicated a preference for a left-hand navigation pattern (common in dashboard-style apps) with content opening beside the nav rather than stacked on the right of the chat.

## Goals
- Introduce a persistent, narrow left-hand navigation bar (icon rail) containing entries for each widget/module: Graph, Notes, Chat History, Map (and any future module panels).
- Clicking a nav bar icon opens that module's panel immediately to the right of the nav bar (left side of the screen), with the chat window filling the remaining space to the right of the open panel.
- Only one module panel is open at a time when launched from the nav bar (selecting a different module swaps the panel; clicking the active module's icon again closes it), keeping the layout predictable.
- Keep the header reserved for identity/account-level controls only: display name, Settings (Config), and Log out — remove Graph/Notes/History/Map buttons from the header.
- Preserve all existing panel functionality (Graph resizing, Notes note-taking mode toggle/exit behavior, History conversation list, Map interactivity) with no behavior regressions.
- Maintain responsive/theme behavior consistent with existing `app-surface`/`app-border`/`app-text` conventions.

## Non-Goals
- No change to the Settings/Config panel's trigger location or behavior — it stays in the top-right header, not the left nav bar.
- No change to the internal implementation of `GraphPanel.vue`, `NotesPanel.vue`, `HistoryPanel.vue`, or `MapPanel.vue` beyond what's needed to fit the new layout container (e.g., removing panel-specific border/positioning classes that assumed a right-side placement).
- No multi-panel-open-at-once support from the nav bar in this version (e.g., Graph + Map open side by side) — that remains a possible Phase 2 enhancement.
- No new widgets/modules are introduced by this spec (Database Connectors tool UI, if built, will plug into this nav bar in its own spec/implementation).
- No changes to authentication, logout, or Settings/Config functionality themselves — only their position is unaffected (they already live in the header).

---

## User Stories
- As a user, I can see a left-hand icon bar with entries for Graph, Notes, History, and Map at all times while chatting.
- As a user, I can click a nav bar icon to open that module's panel on the left, with the chat window still visible on the right.
- As a user, I can click the active module's icon again to close its panel and return to a full-width chat window.
- As a user, I can click a different module icon while one is open and have the panel swap to the newly selected module without extra clicks.
- As a user, I still find my display name, Settings, and Log out in the top-right of the header, unchanged in behavior.

---

## Architecture

### Current Layout (before)
```
┌─────────────────────────────────────────────────────────────┐
│ Header: "AERIAL"      [name][Graph][Notes][History][Config][Map][Logout] │
├─────────────────────────────────────────────────────────────┤
│                                              │Graph/Notes/   │
│              ChatWindow                     │History/Config/│
│              (flex-1)                       │Map (aside)    │
└─────────────────────────────────────────────────────────────┘
```

### New Layout (after)
```
┌─────────────────────────────────────────────────────────────┐
│ Header: "AERIAL"                          [name][Settings][Logout] │
├───┬─────────────────────────────────────────────────────────┤
│ N │             │                                           │
│ a │  Module     │                                           │
│ v │  Panel      │              ChatWindow                   │
│   │  (Graph/    │              (flex-1)                     │
│ b │  Notes/     │                                           │
│ a │  History/   │                                           │
│ r │  Map)       │                                           │
│   │  (only when │                                           │
│   │   selected) │                                           │
└───┴─────────────┴───────────────────────────────────────────┘
```

### Component Map
| Component | File | Change |
|---|---|---|
| App shell | `frontend/src/App.vue` | Add left nav bar; move module panels to render before `ChatWindow`; remove Graph/Notes/History/Map buttons from header; keep name/Settings/Logout in header |
| New nav bar component | `frontend/src/components/NavBar.vue` (new) | Vertical icon rail; emits/selects active module |
| UI/navigation state | `frontend/src/stores/uiStore.ts` (existing — extend) or new `frontend/src/stores/navStore.ts` | Tracks `activeModule: 'graph' \| 'notes' \| 'history' \| 'map' \| null` |
| GraphPanel / NotesPanel / HistoryPanel / MapPanel | `frontend/src/components/*.vue` | Adjust border classes (`border-l` → `border-r` where applicable) since they now sit left-of-chat instead of right-of-chat |

---

## Functional Requirements
1. Add a new `NavBar.vue` component rendered as the left-most element of the authenticated app shell in `App.vue`, with a fixed narrow width (e.g., `w-14`/`w-16`), vertically listing icon buttons for: Graph, Notes, Chat History, Map — reusing the existing SVG icon markup currently in the header buttons for each (see current `toggleGraphPanel`/`toggleNotesPanel`/`toggleHistoryPanel`/`mapStore.toggleMapPanel` buttons in `App.vue`).
2. Each nav bar icon button has `aria-label` and `title` matching its current header equivalent (e.g., "Toggle graph panel" / "Toggle graphs").
3. Selecting a nav bar icon:
   - If no module is active, opens that module's panel.
   - If that module is already active, closes the panel (returns to no module selected / full-width chat).
   - If a different module is active, switches directly to the newly selected module's panel (previous panel closes, new one opens) — no manual close-then-open step required.
4. Only one module panel renders at a time when driven by the nav bar (Graph, Notes, History, Map are mutually exclusive); this replaces today's independent `showGraphPanel`/`showNotesPanel`/`showHistoryPanel`/`mapStore.showMapPanel` booleans that could all be true simultaneously.
5. The active module's panel renders immediately to the right of the nav bar and to the left of `ChatWindow`, using an `<aside>` sized consistently with current panel widths (e.g., `w-96`, and the Graph panel keeps its existing resizable behavior via `startResizeGraphPanel`, with the drag handle now on the panel's right edge since it's adjacent to the chat window on its right instead of left).
6. `ChatWindow` remains `flex-1` and fills all remaining horizontal space to the right of the nav bar (and the module panel, when open).
7. The header (`<header>` in `App.vue`) retains only: app title ("AERIAL"), display name, Settings/Config toggle button, and Log out button. The Graph/Notes/History/Map toggle buttons are removed from the header.
8. Notes-specific behavior is preserved: selecting a different nav bar module (or closing Notes) while note-taking mode is active still calls `notesStore.exitNoteTakingMode()`, mirroring the current `toggleNotesPanel` logic.
9. The Graph panel's auto-open behavior is preserved: the existing `watch(() => chatStore.currentGraphs.length, ...)` that opens the Graph panel when new graphs arrive must now set the nav bar's active module to `'graph'` instead of `showGraphPanel.value = true`.
10. The Settings/Config panel continues to open as it does today (unaffected by nav bar changes) — it is not part of the nav bar's mutually-exclusive module set, and can remain open independently of whichever nav bar module is active (i.e., a user can have both Settings and, say, Notes open at once, matching today's independent-panel behavior for Config).

---

## Frontend Requirements
1. Introduce navigation state — either extend `frontend/src/stores/uiStore.ts` or add a new `frontend/src/stores/navStore.ts` — with:
   - `activeModule: 'graph' | 'notes' | 'history' | 'map' | null` (default `null`).
   - `selectModule(module: 'graph' | 'notes' | 'history' | 'map')` — toggles: sets `activeModule` to the given module, or to `null` if it's already active.
2. Create `frontend/src/components/NavBar.vue`:
   - Renders a vertical `<nav>` with one button per module, reusing existing icon SVGs from `App.vue`.
   - Highlights the active module's icon (e.g., accent color/background), consistent with the existing active-state style used for Notes (`notesStore.noteTakingMode ? 'text-green-500' : 'app-text-muted'`).
   - Emits selection through the nav/ui store rather than local component state, so `App.vue` can react to `activeModule`.
3. Update `frontend/src/App.vue`:
   - Add `<NavBar />` as the first child of `<main>`, before the conditionally-rendered module panel and `ChatWindow`.
   - Replace the four separate `v-if="showGraphPanel"` / `showNotesPanel` / `showHistoryPanel` / `mapStore.showMapPanel` asides with a single conditional block keyed on `activeModule` (e.g., a `<component :is="...">` map or a chain of `v-if`/`v-else-if` on `activeModule === 'graph' | 'notes' | 'history' | 'map'`), rendering `GraphPanel` / `NotesPanel` / `HistoryPanel` / `MapPanel` accordingly, positioned before `ChatWindow` in the DOM/flex order.
   - Remove the four corresponding header buttons (Graph/Notes/History/Map); keep display name, Settings button, and Log out button in the header's right-hand group.
   - Update the Graph panel resize handle (`startResizeGraphPanel`) to sit on the panel's trailing (right) edge, since the panel is now left-of-chat rather than right-of-chat.
4. Adjust panel component styling where it assumed right-side placement:
   - `HistoryPanel.vue` currently uses `border-l app-border` (a left border, appropriate when it sat to the right of chat) — update to `border-r app-border` so the divider appears on the correct edge now that it's left of the chat window.
   - Review `GraphPanel.vue`, `NotesPanel.vue`, `MapPanel.vue`, and `ConfigPanel.vue` for similar left/right border or margin assumptions and correct them for the panel's new position (Config remains on the right per Non-Goals, so it is excluded from this adjustment).
5. Preserve existing Pinia store APIs where reasonably possible (`mapStore.toggleMapPanel()`, `notesStore.exitNoteTakingMode()`) — wire them into the new nav/ui store's `selectModule` flow rather than deleting them outright, to minimize churn in `mapStore.ts`/`notesStore.ts` and their existing tests (`frontend/src/stores/mapStore.test.ts`, `frontend/src/stores/notesStore.test.ts`).

## Backend Requirements
- None. This is a frontend-only layout/navigation restructuring; no API, route, or config changes are required.

## Security/Validation
- No new user input surfaces or trust boundaries are introduced; this is a client-side layout change only.

## Accessibility Requirements
- Nav bar buttons must be keyboard-focusable and operable (native `<button>` elements), each with `aria-label` and `title` matching its function.
- Indicate the active module both visually (icon highlight) and via `aria-pressed="true"` on the active nav bar button for assistive technology.
- Maintain existing focus/keyboard behavior within each panel (Graph/Notes/History/Map) unchanged — only their container position changes.

## Edge Cases
1. Switching modules while Graph panel is mid-resize: resizing state (`graphPanelWidth`) is preserved across module switches since it lives in `App.vue`/parent scope, not destroyed when the panel unmounts.
2. Switching away from Notes while `noteTakingMode` is active: must call `notesStore.exitNoteTakingMode()` exactly as today's `toggleNotesPanel` does, regardless of whether the user closed Notes directly or switched to a different module.
3. New graphs arriving while a different module (e.g., Map) is active: per Functional Requirement 9, the active module switches to `'graph'` automatically, closing whatever was open, matching today's cross-panel auto-open precedent.
4. Rapid repeated clicks on the same nav icon: must cleanly toggle open/closed without duplicate panel mounts (mirrors the Map panel's existing mount/unmount guard from `specs/completed/map-view-widget.spec.md`).
5. Settings/Config panel open together with a nav-bar module: both can coexist since Config is independent of `activeModule`; layout must not overlap/clip either panel (order: NavBar → active module panel → ChatWindow → Config aside, consistent with Config's current right-side position).

## Testing Requirements
- **Frontend (`cd frontend && npm test`)**:
  - New nav/ui store unit tests: default `activeModule` is `null`; `selectModule('graph')` sets it; calling `selectModule('graph')` again resets it to `null`; calling `selectModule('notes')` while `'graph'` is active switches to `'notes'`.
  - `NavBar.vue` component test: renders four buttons with correct `aria-label`s; clicking a button updates the store's `activeModule`; active button has `aria-pressed="true"`.
  - `App.vue` test updates: verify header no longer renders Graph/Notes/History/Map buttons; verify the correct panel component renders based on `activeModule`; verify Settings/Logout/display name remain in the header.
  - Update/verify existing `mapStore.test.ts`/`notesStore.test.ts` continue to pass given any store wiring changes (e.g., `toggleMapPanel` now delegates to `selectModule('map')` if that refactor is chosen).

## Acceptance Criteria
1. A left-hand nav bar is present with icons for Graph, Notes, Chat History, and Map.
2. Selecting a nav bar icon opens the corresponding module panel to the left of the chat window; the chat window remains visible and usable to the right.
3. Selecting the active module's icon again closes the panel, returning to full-width chat.
4. Selecting a different module while one is open swaps directly to the new module without requiring a manual close step.
5. The header's top-right area contains only display name, Settings, and Log out — no Graph/Notes/History/Map buttons remain there.
6. Existing behaviors are preserved with no regressions: Graph panel resize, Notes note-taking-mode exit on close/switch, History conversation list/new chat, Map pan/zoom/reset and session-persisted view, and auto-opening the Graph panel when new graphs arrive.
7. Settings/Config panel continues to function independently of the nav bar, unaffected by this change.
8. All new and existing frontend tests pass via `cd frontend && npm test`.

## Phase 2 Considerations
- Allow multiple nav-bar-launched panels to be open simultaneously (e.g., split view), if user feedback indicates a need.
- Collapsible/expandable nav bar (icon-only vs. icon+label) for wider screens.
- Add the Database Connectors tool (per `specs/database-connectors-and-query-tool.spec.md`) as a new nav bar entry once implemented.
- Drag-to-reorder nav bar entries or user-configurable pinned modules.
