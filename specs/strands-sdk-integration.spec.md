# Spec: Integrate the Strands Agents SDK

## Purpose
Replace the hand-rolled Ollama HTTP client (`StrandsAgentService`) with the
official `strands-agents` Python SDK, giving the AERIAL agent a proper
tool-calling loop, real `@tool` decorated functions, and first-class model
provider support for both Ollama and Gemini.

---

## Problem Statement
`backend/services/strands_agent.py` is named after the Strands SDK but never
uses it. Tools (news search, graph generation) are simulated via
keyword-detection and prompt injection rather than real tool-calling. This
means:

- The LLM cannot decide *when* to invoke a tool — the backend always decides.
- Tool results are injected as raw text rather than structured tool-use turns.
- Adding new tools requires editing the prompt-building logic instead of
  writing a decorated Python function.
- The Gemini provider is also a hand-rolled HTTP client and bypasses the
  existing provider abstraction.

---

## Goals
1. Install `strands-agents` (with the `ollama` and `gemini` extras) and
   `strands-agents-tools`.
2. Replace `StrandsAgentService` with a thin wrapper around
   `strands.Agent(model=OllamaModel(...), tools=[...])`.
3. Replace the Gemini generation path in `ChatService` with
   `strands.Agent(model=GeminiModel(...), tools=[...])`.
4. Convert the existing news-search and graph-generation capabilities into
   proper `@tool` decorated functions that the SDK agent loop can call.
5. Maintain the existing streaming SSE interface (`/api/chat/stream`) and
   the non-streaming interface (`/api/chat/message`) without breaking callers.
6. Maintain the `{ "success": bool, "message": str, "data": ... }` API
   response shape and the `tool_calls` metadata array sent to the frontend.
7. All existing backend tests must continue to pass; new unit tests cover the
   Strands wrapper and each new `@tool` function.

---

## Non-Goals
- No AWS Bedrock integration (no AWS credentials required).
- No MCP server wiring (Phase 2 consideration).
- No changes to the frontend; `tool_calls` metadata shape is preserved.
- No refactor of `GNewsService` or `GeminiService` classes — they stay as
  underlying clients; the `@tool` wrappers delegate to them.
- No changes to authentication, history, config, or notes features.

---

## User Stories
- As a developer, I can add a new tool to the agent by writing a single
  `@tool`-decorated Python function rather than editing prompt-building logic.
- As a user, I send a message asking for news; the LLM decides to call
  `news_search`, receives structured results, and grounds its reply in them.
- As a user, I ask for a chart; the LLM decides to call `generate_graph` and
  the frontend graph panel renders the result as before.
- As an operator, I can switch the provider between Ollama and Gemini via the
  config panel and both providers use the same tool set.

---

## Architecture

```
ChatService
├── _build_strands_agent(provider) → strands.Agent
│   ├── OllamaModel  (provider == "ollama")
│   └── GeminiModel  (provider == "gemini")
│
├── tools/
│   ├── news_search(@tool)   — delegates to GNewsService
│   └── generate_graph(@tool) — produces JSON graph artifact
│
└── stream_message / process_message
    └── calls agent(message) with streaming callback
        └── maps SDK events → existing SSE/metadata shape
```

The `GeminiService` and `StrandsAgentService` classes are **replaced** by
`_build_strands_agent()`. `GNewsService` is kept as a pure HTTP client and
called from inside the `@tool` function.

---

## Backend Requirements

### 1. Dependencies (`backend/requirements.txt`)
- Add `strands-agents[ollama,gemini]` (pinned to a stable release, e.g. `>=1.0,<2`).
- Add `strands-agents-tools` (optional helper tools package).
- Remove no packages from `requirements.txt` in this spec — keep existing ones
  for the fallback period; the old service files are deleted after tests pass.

### 2. New file: `backend/services/strands_tools.py`
Defines the two `@tool` functions available to the agent.

```python
from strands import tool

@tool
def news_search(query: str) -> str:
    """Search recent news articles for the given query.

    Returns a formatted list of article titles, sources, and summaries that
    the agent should use to ground its answer.
    """
    # Receives a GNewsService instance via closure or dependency injection
    ...

@tool
def generate_graph(
    title: str,
    chart_type: str,
    x_label: str,
    y_label: str,
    series_json: str,
) -> str:
    """Emit a chart/graph visualization artifact.

    chart_type must be one of: line, bar, pie.
    series_json is a JSON string: [{"name":"S1","data":[{"x":"A","y":10}]}]
    Returns a confirmation string; the actual artifact is stored on the
    ChatService and returned in the response metadata.
    """
    ...
```

Tool functions must:
- Accept only primitive types as parameters (str, int, float, bool).
- Return `str` (the SDK serialises this into the tool-result turn).
- Not raise unhandled exceptions — catch errors and return an error string.
- Not log or expose API keys.

### 3. New file: `backend/services/strands_provider.py`
Builds and returns a configured `strands.Agent`:

```python
from strands import Agent
from strands.models.ollama import OllamaModel
from strands.models.gemini import GeminiModel

def build_agent(provider: str, config: dict, tools: list) -> Agent:
    if provider == "gemini":
        model = GeminiModel(
            client_args={"api_key": ...},  # from env only
            model_id=config.get("model"),
            params={"temperature": ..., "max_tokens": ...},
        )
    else:  # ollama
        model = OllamaModel(
            host=...,
            model_id=config.get("model"),
        )
    return Agent(model=model, system_prompt=..., tools=tools)
```

### 4. `backend/services/chat_service.py` changes
- Replace `StrandsAgentService` instantiation with `build_agent(provider, config, tools)`.
- Remove `_invoke_ollama`, `_ollama_stream`, and the direct `GeminiService.generate()` calls.
- Replace them with `agent(message)` (non-streaming) and a streaming callback
  approach for SSE.
- Preserve the `tool_calls` metadata array: build it from the SDK's
  `AgentResult.metrics.tool_use` (or equivalent) after each invocation.
- `_wants_visualization` check is removed; the agent decides when to call
  `generate_graph` based on user intent via the LLM.

### 5. Streaming mapping
The Strands SDK `Agent` supports streaming via a callback. Map SDK streaming
events to the existing SSE shape:

| SDK event              | SSE field                |
|------------------------|--------------------------|
| text chunk             | `chunk`                  |
| tool-use start         | `thinking` (tool name)   |
| tool-result            | appended to `tool_calls` |
| completion             | `done: true` + metadata  |

The route handler in `backend/routes/chat.py` is **not changed** — it still
reads from `chat_service.stream_message()` which yields the same dict shape.

### 6. `backend/services/strands_agent.py`
Keep the file during the transition but deprecate it. Delete it only after
all tests pass on the new implementation.

### 7. `backend/services/gemini_service.py`
Keep the class (it is still tested and used by `test_provider_config.py`).
The Gemini *generation* path moves to the SDK; the `GeminiService` class can
remain as a reference but is no longer called from `ChatService`.

---

## Security / Validation
- API keys (`GEMINI_API_KEY`, `GNEWS_API_KEY`) continue to be environment-only;
  never passed into `@tool` docstrings, never logged.
- Tool function inputs (`query`, `series_json`) must be validated for length
  before use (max 500 chars for `query`, max 8 KB for `series_json`).
- `series_json` must be valid JSON; return an error string on parse failure
  rather than raising to the SDK loop.
- No user-supplied content is evaluated as code.

---

## Testing Requirements

### Unit tests (new)
File: `backend/tests/test_strands_tools.py`

1. `news_search` returns formatted article text when `GNewsService` is
   available and returns results.
2. `news_search` returns an informative string when the service is unavailable
   or returns no articles.
3. `news_search` returns an error string (does not raise) when `GNewsService`
   raises an exception.
4. `generate_graph` returns a confirmation string and stores the artifact when
   given valid inputs.
5. `generate_graph` returns an error string when `series_json` is invalid JSON.
6. `generate_graph` returns an error string when `chart_type` is not one of
   `line`, `bar`, `pie`.

File: `backend/tests/test_strands_provider.py`

7. `build_agent` with `provider="ollama"` returns an `Agent` whose model is
   an `OllamaModel`.
8. `build_agent` with `provider="gemini"` returns an `Agent` whose model is a
   `GeminiModel`.
9. `build_agent` falls back to Ollama when `provider="gemini"` but no API key
   is configured.

### Existing tests
- `test_provider_config.py` — must continue to pass unchanged.
- `test_gnews_service.py` — must continue to pass unchanged.
- `test_history_repository_local.py` — must continue to pass unchanged.
- `test_note_repository.py` — must continue to pass unchanged.

---

## Acceptance Criteria
- [ ] `pip install -r backend/requirements.txt` succeeds and includes
  `strands-agents`.
- [ ] `ChatService.stream_message()` routes through the Strands SDK agent loop
  for both Ollama and Gemini providers.
- [ ] Sending a news-related message triggers a real `news_search` tool call
  (visible in `tool_calls` metadata).
- [ ] Sending a chart-related message triggers a real `generate_graph` tool
  call and the frontend Graph Panel renders the result.
- [ ] `python -m pytest tests/ -v` passes with no regressions.
- [ ] The SSE stream shape (`chunk`, `done`, `thinking`, `tool_calls`,
  `conversation_id`) is unchanged as observed by the frontend.
- [ ] No API keys appear in logs or API responses.

---

## Phase 2 Considerations
- **MCP support**: expose an MCP server so external tools (file system,
  browser, databases) can be wired in without code changes.
- **Additional strands-agents-tools**: evaluate built-in tools (calculator,
  Python REPL, HTTP fetch) for inclusion.
- **Multi-agent patterns**: route complex requests to a sub-agent (e.g. a
  dedicated research agent backed by a more capable model).
- **Bedrock provider**: add `BedrockModel` as a third provider option behind a
  feature flag, for users with AWS credentials.
