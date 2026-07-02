# Spec: Gemini API Offload Tool for Agent

## Purpose
Enable the agent to offload a task to Google's Gemini API when the local Ollama model is not well suited to handle it — for example, complex reasoning, very long context, code generation, or multimodal input. The agent decides (or is configured) to delegate a task to Gemini, receives the result, and incorporates it into its response.

## Problem Statement
The agent currently runs exclusively against a local Ollama model. Local models are private and cost-free but may be limited in reasoning quality, context window, or capabilities compared to a frontier cloud model. There is no mechanism for the agent to selectively delegate a difficult task to a more capable model and merge the result back into the conversation.

## Goals
- Provide the agent with a tool that sends a task/prompt to the Gemini API and returns the result.
- Support explicit offloading (user/config requests Gemini) and heuristic offloading (agent detects a task that warrants a stronger model).
- Keep local Ollama as the default; Gemini is an opt-in, configurable fallback/augmentation path.
- Surface to the user when a response (or part of it) was produced by Gemini.
- Keep the tool modular so the cloud provider can be swapped (e.g., OpenAI, Anthropic) without changing the agent interface.

## Non-Goals
- No replacement of the local Ollama model as the primary agent runtime.
- No streaming of Gemini partial tokens in Phase 1 (return the full offloaded result).
- No fine-tuning, no Gemini file/context caching, no multi-turn Gemini session state.
- No automatic cost management/budgeting UI (basic usage logging only).

---

## User Stories
- As a user, I can ask a complex question and have the agent transparently delegate it to Gemini for a higher-quality answer.
- As a user, I can explicitly request the agent to "use Gemini" for a task.
- As a user, I can see when a response was produced or assisted by Gemini (source indicator).
- As an admin, I can enable/disable Gemini offloading and provide an API key via configuration.
- As an admin, I can configure which Gemini model is used and the offload trigger behavior.

---

## Architecture

### High-Level Flow
```
User Message
    │
    ▼
┌─────────────────┐
│  Chat Service    │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  Agent Service       │
│  (Ollama LLM)        │
└────────┬────────────┘
         │ Offload decision (explicit or heuristic)
         │ Tool call: gemini_offload(task, context)
         ▼
┌─────────────────────┐
│  Gemini Offload Tool │
│  (Provider Layer)    │
└────────┬────────────┘
         │ HTTPS request
         ▼
┌─────────────────────┐
│  Gemini API          │
│  (generativelanguage)│
└────────┬────────────┘
         │
         ▼
   Offloaded result returned to agent,
   merged into response with source metadata
```

---

## Functional Requirements

### Gemini Offload Tool

1. The tool must accept a `task` prompt string and optional `context` (conversation history / retrieved context) and return the generated text.
2. The tool must return results with: `content` (text), `model` (Gemini model used), `provider` (`"gemini"`), and `usage` (token counts when available).
3. The tool must handle API errors gracefully (auth failure, rate limit, timeout, network error) and return a structured error, never crash the request.
4. On any Gemini failure, the agent must fall back to the local Ollama model and still return a response.
5. Requests must respect a configurable timeout (`gemini.timeout_seconds`, default 60).
6. The tool must never log or echo the API key.

### Offload Decision

7. **Explicit offload**: if the user message contains an explicit request (e.g., "use gemini", "ask gemini", "offload this"), the agent routes the task to Gemini.
8. **Heuristic offload** (optional, config-gated by `gemini.auto_offload`): the agent may route to Gemini when it detects a task type that benefits from a stronger model (e.g., long input exceeding a token threshold, complex code generation, explicit reasoning requests). Heuristics must be conservative and documented.
9. When offloading is disabled, the tool must not be invoked and the agent responds with Ollama only.
10. The offload decision and outcome must be recorded in the message metadata (`offloaded: bool`, `provider`, `model`).

### Agent Integration

11. The Gemini offload tool must be registered with the agent service so it can be invoked during response generation.
12. When Gemini returns a result, the content is used as (or merged into) the agent's response, and `tool_calls`/metadata records the offload.
13. The system prompt / offload prompt must pass along the relevant conversation context so Gemini has the necessary background.
14. Response metadata must clearly indicate the source model so the frontend can display it.

---

## Backend Requirements

### New Configuration

Add to `config.py` / `.env`:

```python
# Gemini Offload
GEMINI_ENABLED = os.getenv('GEMINI_ENABLED', 'False') == 'True'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
GEMINI_BASE_URL = os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta')
GEMINI_TIMEOUT_SECONDS = int(os.getenv('GEMINI_TIMEOUT_SECONDS', '60'))
GEMINI_MAX_OUTPUT_TOKENS = int(os.getenv('GEMINI_MAX_OUTPUT_TOKENS', '2048'))
GEMINI_TEMPERATURE = float(os.getenv('GEMINI_TEMPERATURE', '0.7'))
GEMINI_AUTO_OFFLOAD = os.getenv('GEMINI_AUTO_OFFLOAD', 'False') == 'True'
GEMINI_AUTO_OFFLOAD_CHAR_THRESHOLD = int(os.getenv('GEMINI_AUTO_OFFLOAD_CHAR_THRESHOLD', '8000'))
```

Add to `DEFAULT_CONFIG`:

```python
'gemini': {
    'enabled': GEMINI_ENABLED,
    'model': GEMINI_MODEL,
    'base_url': GEMINI_BASE_URL,
    'timeout_seconds': GEMINI_TIMEOUT_SECONDS,
    'max_output_tokens': GEMINI_MAX_OUTPUT_TOKENS,
    'temperature': GEMINI_TEMPERATURE,
    'auto_offload': GEMINI_AUTO_OFFLOAD,
    'auto_offload_char_threshold': GEMINI_AUTO_OFFLOAD_CHAR_THRESHOLD
}
```

> Note: `GEMINI_API_KEY` is a secret and must **only** be read from the environment, never stored in `DEFAULT_CONFIG` or returned by the config API.

### New Service: `services/gemini_service.py`

```python
class GeminiService:
    def __init__(self, config: dict, api_key: str):
        """Initialize with Gemini configuration and API key (from env)."""

    def is_available(self) -> bool:
        """Return True if Gemini is enabled and an API key is present."""

    def offload(self, task: str, context: list[dict] | None = None) -> dict:
        """Send a task to the Gemini API and return the result.
        Returns: {
            'content': str,
            'model': str,
            'provider': 'gemini',
            'usage': { 'input_tokens': int, 'output_tokens': int } | None
        }
        Raises/returns structured error on failure (caller falls back to Ollama)."""
```

Implementation notes:
- Call `POST {base_url}/models/{model}:generateContent?key=API_KEY` with a `contents` payload built from `context` + `task`.
- Map `generationConfig` to `temperature` and `maxOutputTokens` from config.
- Extract text from `candidates[0].content.parts[*].text`.
- Extract token counts from `usageMetadata` when present.
- Use `requests` with the configured timeout (consistent with `strands_agent.py`).

### Agent / Chat Service Integration

- `StrandsAgentService` (or `ChatService`) gains an offload decision step:
  - Detect explicit offload keywords or apply heuristic (`auto_offload` + char threshold).
  - If offloading and `GeminiService.is_available()`, call `offload(...)`.
  - On success, use Gemini content and set metadata `{ offloaded: true, provider: 'gemini', model: <model> }`.
  - On failure or when disabled, proceed with the normal Ollama path.
- The `tool_calls` metadata field (already present) records the offload invocation.

### New Endpoints

#### `GET /api/gemini/status`
Return current Gemini offload availability and configuration (no secret values).

**Success Response:**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "enabled": true,
    "available": true,
    "model": "gemini-1.5-flash",
    "auto_offload": false
  }
}
```

#### `POST /api/gemini/offload`
Direct offload endpoint for testing/debugging.

**Request:**
```json
{
  "task": "Refactor this function for readability and explain the changes.",
  "context": []
}
```

**Success Response:**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "content": "Here is the refactored function...",
    "model": "gemini-1.5-flash",
    "provider": "gemini",
    "usage": { "input_tokens": 120, "output_tokens": 340 }
  }
}
```

**Error Response (e.g., disabled or missing key):**
```json
{
  "success": false,
  "message": "Gemini offload is not available",
  "data": null
}
```

---

## Frontend Requirements (Future — Out of Scope for Phase 1)

For Phase 1, Gemini offload is configured via `.env` and observable via API/metadata. Future UI enhancements:

- Source indicator on messages that were offloaded (e.g., an "answered by Gemini" badge).
- Config panel toggle for `enabled` and `auto_offload` (API key remains env-only).
- Gemini status indicator (available/unavailable) in the config panel.
- Optional per-message "Ask Gemini" action to re-run a response through Gemini.

---

## New Dependencies

No new required dependencies — the existing `requests` library is sufficient for the Gemini REST API.

Optional (if the official SDK is preferred over raw REST):

```
google-generativeai>=0.7.0
```

---

## File Structure

```
backend/
  services/
    gemini_service.py     # New — Gemini API client and offload logic
  routes/
    gemini.py             # New — /api/gemini/status and /api/gemini/offload
```

---

## Security Requirements

1. `GEMINI_API_KEY` must be read from the environment only; never stored in `DEFAULT_CONFIG`, returned by any config/status endpoint, or written to logs.
2. All Gemini requests use HTTPS.
3. Redact the API key from any error messages before logging.
4. The offload endpoints must respect existing authentication (if `AUTH_ENABLED`).
5. Apply the configured timeout to prevent hanging requests; fail closed to the local model.

---

## Testing Requirements

1. **Unit tests** for the offload decision (explicit keyword detection; heuristic threshold; disabled state).
2. **Unit tests** for `GeminiService.offload` request building and response parsing (mock the HTTP call).
3. **Unit tests** for error handling and fallback (auth error, timeout, malformed response → structured error, no crash).
4. **Integration test**: `/api/gemini/offload` returns the mocked Gemini result with the correct schema.
5. **Edge cases**:
   - Gemini disabled → tool not invoked, Ollama response returned.
   - Missing API key → `available: false`, offload not attempted.
   - Gemini API failure → agent falls back to Ollama and still responds.
   - API key never appears in logs or API responses.

---

## Phase 2 Considerations (Future)

- **Streaming**: stream Gemini partial tokens via the existing SSE `/api/chat/stream` path.
- **Multimodal offload**: pass images/files to Gemini for vision tasks.
- **Provider abstraction**: generalize into a `CloudOffloadService` supporting Gemini, OpenAI, Anthropic behind one interface.
- **Smart routing**: learn/route by task type and measured quality, not just heuristics.
- **Cost tracking**: aggregate token usage and expose usage/cost metrics.
- **Caching**: cache identical offload requests to reduce API calls.
