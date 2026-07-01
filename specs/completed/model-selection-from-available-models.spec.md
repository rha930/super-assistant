# Spec: Change Models from Available Model List

## Purpose
Allow users to select and switch the agent model from a backend-provided list of available models (e.g., Ollama pulled models).

## Problem Statement
Users currently must manually edit configuration to change models and may choose invalid names, causing runtime failures.

## Goals
- Present a validated list of available models in configuration UI.
- Enable model switching through a dropdown/select input.
- Prevent selecting unavailable models.

## Non-Goals
- No automatic model recommendations.
- No model download/pull workflow in this feature (future enhancement).

## User Stories
- As a user, I can see models that are currently available.
- As a user, I can choose a model from the list and save it.
- As a user, I get clear feedback if the selected model is not available anymore.

## Functional Requirements
1. Backend must expose endpoint to list available models.
2. Frontend config panel must fetch and display available model list.
3. UI control must be a select/dropdown bound to `config.model`.
4. Save operation must validate selected model exists in available list.
5. If selected model disappears before save, block save and show validation error.
6. If current model is not in list, show warning state and keep value visible until changed.

## Backend Requirements

### New Endpoint
- `GET /api/models`

### Endpoint Behavior
- Query local model runtime (Ollama `/api/tags`).
- Return normalized model names.
- Return empty list with success if runtime reachable but no models present.
- Return 503 with structured error if runtime unreachable.

### Success Response Example
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "models": [
      "llama3.1:8b",
      "mistral:7b",
      "gemma3:4b"
    ]
  }
}
```

### Error Response Example
```json
{
  "success": false,
  "message": "Unable to fetch models from local runtime",
  "code": "MODEL_LIST_UNAVAILABLE",
  "details": {}
}
```

## Frontend Requirements
1. Add API call in service layer:
   - `GET /api/models`
2. Extend config store with:
   - `availableModels: string[]`
   - `loadAvailableModels()`
3. Config panel behavior:
   - Show model dropdown populated from `availableModels`.
   - Selected value maps to `config.model`.
   - Disable save while models are loading (initial fetch only).
   - Show empty-state hint if no models found: "No local models available. Pull a model first." 
4. Validation:
   - Save blocked if selected model is empty.
   - Save blocked if model not in latest available list.

## UX Requirements
- Section title: "Model Selection".
- Field label: "Model".
- Show a refresh icon/button near dropdown to reload model list.
- Show current active model badge even when dropdown is empty.
- Non-blocking warning banner when current model is stale/unavailable.

## Data & State Requirements
- `config.model` remains persisted backend-side via existing config endpoint.
- `availableModels` is frontend ephemeral state and refreshed on panel open.
- Keep selected model stable during transient fetch failures.

## Edge Cases
1. Runtime unreachable while opening panel:
   - Show warning, preserve current selected model.
2. No models available:
   - Dropdown disabled, save blocked, helper text visible.
3. Current model removed externally:
   - Show stale warning; allow user to choose another available model.
4. Race condition between list refresh and save:
   - Validate against latest in-memory list before submit.

## Security/Validation Considerations
- Treat model names as untrusted input from runtime.
- Render as plain text in dropdown/options.
- Backend should sanitize and validate selected model string length/content.

## Acceptance Criteria
1. Config panel shows selectable dropdown of available models from backend.
2. User can switch model and save; backend persists and uses new model for next chat.
3. Invalid/unavailable model cannot be saved from UI.
4. App handles runtime unavailability with clear non-crashing errors.

## Test Cases
- Unit: model list mapping and sorting in store.
- Unit: save validation fails for unavailable model.
- Integration: fetch models -> select -> save -> chat uses selected model.
- Integration: model list endpoint 503 -> warning UI appears, app remains functional.
- E2E: change model and verify response metadata includes selected model.

## Implementation Notes
- Recommended backend placement: new route file or add endpoint to existing config/health route module.
- Prefer lexicographic sorting of models for predictable dropdown UX.
- Keep endpoint fast; avoid blocking chat path.
