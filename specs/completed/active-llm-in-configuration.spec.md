# Spec: Show Active LLM in Configuration Settings

## Purpose
Display the currently active LLM (the model in use by the agent) in the configuration UI so users can confirm what model is being used for chat generation.

## Problem Statement
Users cannot easily verify which model is currently active. This creates confusion when behavior changes after model updates or environment changes.

## Goals
- Show the active model clearly in the configuration panel.
- Ensure displayed model matches backend runtime configuration.
- Keep model display in sync after config updates and app refresh.

## Non-Goals
- No model benchmarking/performance scoring in this feature.
- No multi-model routing logic in this feature.

## User Stories
- As a user, I can open configuration and see the active LLM.
- As a user, I can trust the displayed model reflects what the backend is actually using.

## Functional Requirements
1. Configuration panel must include an "Active Model" field.
2. On panel open, frontend must fetch model from backend config endpoint.
3. If model is not explicitly set, backend must return resolved/default model value.
4. When model is updated and saved, UI must immediately reflect updated active model.
5. If backend cannot resolve model, UI shows fallback text: "No active model configured".

## UX Requirements
- Placement: Top section of configuration panel, above model parameters.
- Label: "Active Model".
- Value styling: Monospace badge/chip style for readability.
- Loading state: Skeleton/placeholder while config is loading.
- Error state: Inline warning if config fetch fails.

## Backend Requirements
- Existing endpoint `GET /api/config` must include `model` in response data.
- Existing endpoint `POST /api/config` must persist updated `model`.
- Config service must return resolved model when empty (fallback to runtime default).

### Response Contract
`GET /api/config` success payload data should include:
```json
{
  "model": "llama3.1:8b",
  "model_parameters": {
    "temperature": 0.7,
    "max_tokens": 1000,
    "top_p": 0.9
  },
  "system_prompt": "...",
  "agent_config": {
    "max_iterations": 10,
    "timeout": 30
  }
}
```

## Frontend Requirements
- Update config store shape to include `model: string`.
- Update config panel component to render active model.
- Ensure `loadConfig()` populates model in state.
- Ensure `saveConfig()` sends model when present.

## Data Validation Rules
- `model` must be a non-empty string when set.
- Trim surrounding whitespace before save.

## Edge Cases
- Backend returns empty model: show fallback label and warning icon.
- Backend unavailable: display non-blocking error and preserve last known model in UI state.

## Telemetry (Optional)
- Event: `config_active_model_loaded`
  - Properties: `model`, `source` (`backend` | `fallback`)

## Acceptance Criteria
1. Opening configuration always shows an "Active Model" value or explicit fallback text.
2. After saving configuration with a new model, the displayed active model updates without page refresh.
3. Refreshing the app preserves and re-displays the same active model from backend config.
4. No regression in chat send/stream functionality.

## Test Cases
- Unit: config store maps backend `model` correctly.
- Unit: config panel renders model chip with provided value.
- Integration: update config model -> save -> reopen panel -> model persists.
- Integration: backend returns empty model -> fallback text is shown.

## Implementation Notes
- Prefer single source of truth: backend config response.
- Avoid duplicating inferred model logic in frontend where possible.
