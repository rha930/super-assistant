# Spec: Add Dark Mode Theme Toggle

## Purpose
Provide a full dark mode experience across the application with a user-controlled theme toggle and persisted preference.

## Problem Statement
The UI currently appears in a single visual mode, which can reduce readability and comfort in low-light environments and does not meet user expectations for theme personalization.

## Goals
- Add dark mode styling across all major UI surfaces.
- Provide an accessible toggle for switching between light and dark themes.
- Persist user theme preference across page reloads.
- Respect system color scheme when user has not made an explicit choice.

## Non-Goals
- No per-component custom theming beyond app-wide light/dark modes.
- No user-defined color palette editor in this feature.
- No redesign of layout or interaction flows unrelated to theme support.

## User Stories
- As a user, I can switch between light and dark mode from the UI.
- As a user, my selected theme is remembered the next time I open the app.
- As a user, if I do not pick a theme, the app follows my OS/system theme.

## Functional Requirements
1. App must support three theme states internally:
   - `light`
   - `dark`
   - `system`
2. Default theme state must be `system` for first-time users.
3. Theme toggle control must be available in a visible, consistent location.
4. Selecting `light` or `dark` must apply immediately without page reload.
5. Theme preference must be persisted in browser storage.
6. On app startup, theme resolution must follow:
   - use explicit stored preference if present (`light` or `dark`)
   - otherwise resolve from system preference when state is `system`
7. If system preference changes while app is open and state is `system`, theme must update automatically.

## UX Requirements
- Add a clear theme control in top-level UI (header/toolbar/settings entry).
- Control options:
  - Light
  - Dark
  - System
- Include iconography and text labels to avoid ambiguity.
- Ensure no flash of incorrect theme after initial load (avoid noticeable FOUC).
- Provide visible focus states and keyboard operability for toggle control.

## Accessibility Requirements
- Maintain WCAG-compliant contrast in both light and dark modes for primary text and interactive controls.
- Toggle must be reachable and operable via keyboard.
- Toggle labels and state must be screen-reader accessible (aria label/state or equivalent semantic control).
- Do not use color alone to indicate active theme selection.

## Frontend Requirements
1. Add theme state management to UI store (`light|dark|system`, resolved mode).
2. Add methods/actions:
   - `setTheme(mode)`
   - `initializeTheme()`
   - `applyResolvedTheme()`
3. Apply theme via root-level class or data attribute on document element (e.g., `dark` class or `data-theme`).
4. Update global styles (`src/style.css`) to define tokenized theme variables for both modes.
5. Update key components to consume theme variables instead of hardcoded colors:
   - Chat window
   - Message bubbles/content
   - Configuration panel
   - Buttons/inputs/cards
6. Add a theme toggle UI component or integrate toggle into existing top-level component.

## Styling Requirements
- Define CSS custom properties for semantic tokens (example categories):
  - `--color-bg`
  - `--color-surface`
  - `--color-text`
  - `--color-text-muted`
  - `--color-border`
  - `--color-accent`
  - `--color-accent-contrast`
- Light and dark variants must be centrally defined and reused.
- Remove hardcoded hex values in core UI where practical for theme-aware surfaces.

## Persistence Requirements
- Store theme preference in localStorage key: `ui.theme`.
- Valid stored values:
  - `light`
  - `dark`
  - `system`
- Invalid stored values must fall back to `system`.

## Edge Cases
1. localStorage unavailable or blocked:
   - Theme still applies for session; fail gracefully without crash.
2. User switches OS theme while app open and selected state is `system`:
   - App updates theme in real time.
3. Legacy hardcoded colors in component styles:
   - Must be identified and migrated for major surfaces covered by this spec.

## Telemetry (Optional)
- Event: `theme_changed`
  - Properties: `selected_theme`, `resolved_theme`, `source` (`toggle`|`startup`|`system-change`)

## Acceptance Criteria
1. User can switch between Light, Dark, and System themes from the app UI.
2. Theme changes apply immediately without reload.
3. Chosen theme persists after refresh/reopen.
4. When set to System, app follows OS theme and reacts to OS theme changes live.
5. Core screens/components render with readable contrast in dark mode.
6. No regression in existing chat/config functionality.

## Test Cases
- Unit:
  - Theme store initializes correctly from localStorage and system preference.
  - Invalid stored values fallback to `system`.
  - Resolved theme calculation returns expected mode.
- Component:
  - Theme toggle control emits and updates state correctly.
  - Root theme class/attribute updates when state changes.
- Integration:
  - Set dark mode, refresh app, verify dark mode persists.
  - Set system mode, simulate system preference change, verify live theme update.
  - Verify key components use theme tokens and remain readable.
- Accessibility:
  - Keyboard navigation and activation of toggle.
  - Screen reader label/state verification.

## Implementation Notes
- Prefer theme tokens over one-off component overrides.
- Keep store as single source of truth for selected and resolved theme.
- Initialize theme as early as possible in app bootstrap to reduce flash.
- If using Tailwind dark mode utilities, align with chosen root selector strategy (`class` or `media`) and ensure consistency across custom CSS.
