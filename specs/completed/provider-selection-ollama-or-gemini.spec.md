# Spec: Select LLM Provider (Ollama or Gemini) in Configuration

## Purpose
Add a provider selector to the configuration menu so users can choose whether the agent runs against the local **Ollama** runtime or the **Gemini API**. Selecting Gemini routes chat generation to Gemini instead of the local model.

## Problem Statement
The agent is hardwired to the local Ollama runtime. Users who want higher-quality or cloud-based responses have no way to switch providers from the UI. Provider choice should be a first-class configuration option alongside model selection and model parameters.

## Problem vs. Related Spec
This spec differs from `gemini-offload-tool.spec.md`:
- **Offload spec**: Ollama stays primary; individual tasks are *delegated* to Gemini opportunistically.
- **This spec**: the user *explicitly selects the active provider* in the config menu; all chat generation uses the selected provider until changed.

They can coexist — this spec introduces the provider switch; the offload spec covers per-task delegation. Implementation should reuse a shared `GeminiService` if both are built.

## Goals
- Add a `provider` field to configuration with values `"ollama"` (default) and `"gemini"`.
- Add a provider dropdown to the config panel.
- Route chat generation to the selected provider in the backend.
- Show provider-appropriate model options (Ollama model list vs. Gemini model list).
- Indicate the active provider in the UI and in response metadata.
- Fail gracefully when Gemini is selected but unavailable (missing key / disabled).

## Non-Goals
- No new offload/delegation heuristics (covered by the offload spec).
- No streaming changes beyond routing (Phase 1 may return non-streamed Gemini output if streaming is not yet implemented).
- No storage of the Gemini API key in the UI or config payload — key remains environment-only.
- No multi-provider simultaneous use in a single response.

---

## User Stories
- As a user, I can open the config menu and choose "Ollama (local)" or "Gemini (cloud)" as the provider.
- As a user, when I pick a provider, the model dropdown updates to that provider's available models.
- As a user, I can save the provider choice and my next chat uses that provider.
- As a user, I see which provider produced a response.
- As an admin, I can disable Gemini so it does not appear as a selectable option (or appears disabled with a hint).

---

## Architecture

### High-Level Flow
```
Config Menu (provider select)
    │  save { provider: "ollama" | "gemini", model, ... }
    ▼
┌─────────────────┐
│  Config Service  │  persists provider + model
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Chat Service    │  reads config.provider
└────────┬────────┘
         │ provider == "gemini"?
         ├───────────── yes ──────────────┐
         │ no                              ▼
         ▼                        ┌────────────────┐
┌────────────────┐                │ Gemini Service  │
│ Strands Agent   │                │ (Gemini API)    │
│ (Ollama)        │                └────────────────┘
└────────────────┘
```

---

## Functional Requirements

1. Configuration gains a `provider` field: `"ollama"` (default) or `"gemini"`.
2. The config panel shows a **Provider** dropdown above the Model field.
3. When the provider changes, the Model dropdown repopulates with that provider's models:
   - Ollama → existing `GET /api/models` list.
   - Gemini → a configured list of allowed Gemini models (from `GET /api/gemini/models` or a static config list).
4. The backend routes chat generation to the selected provider for both `process_message` and `stream_message`.
5. Response metadata must include `provider` and `model` used.
6. If `provider == "gemini"` but Gemini is unavailable (disabled or no API key):
   - The config panel shows the Gemini option as disabled with a hint, OR
   - Saving Gemini is blocked with a validation message, AND
   - If somehow selected at runtime, the backend falls back to Ollama and flags it in metadata.
7. Switching providers must not lose the previously selected per-provider model (retain last model per provider where feasible).

---

## Backend Requirements

### Configuration

Add a `provider` key to `DEFAULT_CONFIG` in `config.py`:

```python
# Provider selection
AGENT_PROVIDER = os.getenv('AGENT_PROVIDER', 'ollama')  # 'ollama' | 'gemini'
```

```python
DEFAULT_CONFIG = {
    'provider': AGENT_PROVIDER,
    'model': AGENT_MODEL,
    # ...existing keys...
}
```

Reuse the Gemini settings from `gemini-offload-tool.spec.md` (`GEMINI_ENABLED`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_BASE_URL`, etc.). The API key remains environment-only and must never be returned by the config API.

### `config_service.py`

Extend `update_config` to accept and validate `provider`:

```python
if 'provider' in new_config:
    provider = str(new_config.get('provider') or 'ollama').strip().lower()
    if provider not in ('ollama', 'gemini'):
        provider = 'ollama'
    self.config['provider'] = provider
```

- `get_config` returns `provider` (defaulting to `'ollama'`).
- Validation: if `provider == 'gemini'` and Gemini is not enabled/available, `update_config` should reject with a clear error (or coerce to `ollama` and log a warning — choose reject for explicit UX).

### `chat_service.py`

- Read `provider` from the active config.
- If `provider == 'gemini'` and `GeminiService.is_available()`, route generation through `GeminiService`; otherwise use `StrandsAgentService` (Ollama).
- On Gemini runtime failure, fall back to Ollama and set metadata `{ provider: 'ollama', fallback_from: 'gemini' }`.
- Set response metadata `{ provider, model }` in both `process_message` and `stream_message`.

### Shared Service: `services/gemini_service.py`
Reuse the `GeminiService` defined in `gemini-offload-tool.spec.md`. For this spec it needs a generation method compatible with the chat flow (accepts message + conversation history + model parameters, returns content / streams chunks).

### New / Updated Endpoints

#### `GET /api/gemini/models`
Return the list of selectable Gemini models (static allow-list from config, e.g. `gemini-1.5-flash`, `gemini-1.5-pro`). Returns empty list if Gemini is disabled.

**Success Response:**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "models": ["gemini-1.5-flash", "gemini-1.5-pro"],
    "available": true
  }
}
```

#### `GET /api/config` (updated)
Now includes `provider` in the returned config.

#### `POST /api/config` (updated)
Accepts `provider`. Validates as described above.

---

## Frontend Requirements

### Config Store (`configStore.ts`)

1. Add `provider` to the `Config` interface and `DEFAULT_CONFIG`:
   ```ts
   interface Config {
     provider: 'ollama' | 'gemini'
     model: string
     // ...existing
   }
   ```
   Default `provider: 'ollama'`.
2. Add state and loaders for Gemini models and availability:
   - `geminiModels: string[]`
   - `geminiAvailable: boolean`
   - `loadGeminiModels()` → `GET /api/gemini/models`
3. Expose a computed `activeModels` that returns `availableModels` when provider is `ollama`, else `geminiModels`.
4. Optionally retain last-selected model per provider so switching back restores it.

### Config Panel (`ConfigPanel.vue`)

1. Add a **Provider** dropdown above the Model section:
   ```
   Provider: [ Ollama (local) ▾ ]
             [ Gemini (cloud)   ]
   ```
   - Bind to `config.provider`.
   - Disable the "Gemini (cloud)" option (with a hint) when `!geminiAvailable`.
2. When `provider` changes:
   - Repopulate the Model dropdown from `activeModels`.
   - Reset/adjust `config.model` to a valid model for the new provider.
   - Trigger `loadGeminiModels()` (once) when Gemini is selected.
3. Show an active-provider badge alongside the model badge.
4. Validation before save:
   - Block save if `provider == 'gemini'` and `!geminiAvailable`.
   - Block save if selected `model` is empty or not in `activeModels`.
5. Reuse the existing stale-model / runtime-error warning patterns for the Gemini list too.

---

## UX Requirements
- Section title: "Provider".
- Field label: "Provider" with options "Ollama (local)" and "Gemini (cloud)".
- When Gemini is unavailable, show helper text: "Gemini is not configured. Add an API key to enable it."
- Model dropdown label and behavior remain as in `model-selection-from-available-models.spec.md`, but sourced from the active provider.
- Show provider in response/message metadata (e.g., a small "via Gemini" / "via Ollama" indicator — full UI badge is a future enhancement).

---

## Data & State Requirements
- `config.provider` and `config.model` persist backend-side via the existing config endpoint.
- `geminiModels` / `geminiAvailable` are frontend ephemeral state, refreshed when the panel opens or Gemini is selected.
- Keep provider/model selection stable during transient fetch failures.

---

## Security / Validation Considerations
- `GEMINI_API_KEY` is environment-only; never sent to or from the frontend, never in config payloads or logs.
- Validate `provider` against the allow-list `{ ollama, gemini }` on the backend.
- Treat Gemini model names as an allow-listed set; reject arbitrary model strings.
- All Gemini requests over HTTPS with the configured timeout; fail closed to Ollama.
- Respect existing authentication on config and model-list endpoints.

---

## Edge Cases
1. Gemini selected but API key missing → save blocked (or runtime fallback to Ollama with metadata flag).
2. Provider switched to Gemini while offline/unreachable → warning shown; save allowed only if `available`, runtime falls back on failure.
3. Current model invalid for newly selected provider → auto-select first available model or show stale warning.
4. Gemini disabled by admin after being selected → panel shows unavailable state; next save must switch to Ollama.
5. Race between provider switch and model-list fetch → validate against latest in-memory list before submit.

---

## Testing Requirements

1. **Unit (backend)**: `update_config` accepts `ollama`/`gemini`, rejects invalid provider, rejects/coerces Gemini when unavailable.
2. **Unit (backend)**: chat service routes to Gemini vs. Ollama based on `provider`; falls back to Ollama on Gemini failure with correct metadata.
3. **Unit (frontend)**: `activeModels` computed switches lists by provider; save validation blocks unavailable Gemini and invalid models.
4. **Integration**: set provider to Gemini → chat request routes to mocked Gemini and returns metadata `provider: "gemini"`.
5. **Integration**: `GET /api/config` returns `provider`; `POST /api/config` persists it.
6. **Edge cases**: Gemini disabled → option disabled/hidden; missing key → fallback path exercised; provider switch preserves per-provider model.

---

## Acceptance Criteria
1. Config panel shows a Provider dropdown with Ollama and Gemini options.
2. Selecting Gemini shows Gemini models; selecting Ollama shows local models.
3. Saving the provider persists it and the next chat uses the selected provider.
4. Response metadata reports the provider and model actually used.
5. Gemini unavailable is handled with clear, non-crashing UX and safe backend fallback.

---

## Phase 2 Considerations (Future)
- Provider badge rendered inline on each message.
- Per-conversation provider override (not just global config).
- Additional providers (OpenAI, Anthropic) via the same selector and a generalized provider interface.
- Streamed Gemini output through the existing SSE `/api/chat/stream` path.
- Dynamic Gemini model discovery via the Gemini `models.list` API instead of a static allow-list.
