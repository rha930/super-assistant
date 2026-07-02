# Spec: Tavily Web Search Tool for Agent

## Purpose
Give the agent a web search tool powered by the [Tavily API](https://tavily.com/) so it can retrieve current, real-time information from the internet and incorporate it into responses.

## Problem Statement
The agent currently relies solely on the LLM's training data and conversation history. It has no access to live information — breaking news, current prices, recent documentation, or any data that post-dates the model's training cutoff. Users asking time-sensitive questions receive stale or hedged answers ("As of my last update…"). A web search tool closes this gap by letting the agent fetch relevant, up-to-date content on demand.

## Goals
- Provide a `TavilyService` that wraps the Tavily Search API and can be invoked as an agent tool.
- The agent automatically decides when a query needs web search (e.g., current events, recent data, "search for…" requests).
- Inject search results into the LLM prompt context so the response is grounded in live data.
- Surface search tool usage in response metadata (`tool_calls`) so the activity indicator spec can render it.
- Keep the tool modular — the search provider can be swapped (e.g., SerpAPI, Brave Search) without changing the agent interface.
- Support both Ollama and Gemini providers as the primary LLM; the search tool augments either.

## Non-Goals
- No full web browsing / page rendering — search returns text snippets, not full page content.
- No caching layer for search results in Phase 1.
- No user-facing search UI (the agent decides when to search; users don't trigger it manually).
- No image or video search.
- No cost management / quota UI — basic usage logging only.
- No Tavily Extract or Crawl endpoints — search only.

---

## User Stories
- As a user, I can ask the agent about current events and receive an answer grounded in live web data.
- As a user, I can see when the agent performed a web search (tool activity indicator).
- As a user, I can see the sources the agent used in its response.
- As an admin, I can enable/disable web search and provide a Tavily API key via environment variables.
- As an admin, I can configure search depth, max results, and domain include/exclude lists.

---

## Architecture

### High-Level Flow
```
User Message
    │
    ▼
┌───────────────────┐
│   Agent Service    │  (Ollama or Gemini)
│   (LLM Provider)  │
└────────┬──────────┘
         │  Agent detects need for current data
         ▼
┌───────────────────┐       ┌──────────────────┐
│  Search Decision  │──────▶│  Tavily Service   │
│  (heuristic /     │       │  (REST API call)  │
│   LLM judgment)   │       └────────┬─────────┘
└───────────────────┘                │
         │◀──────── search results ──┘
         ▼
┌───────────────────┐
│  LLM generates    │
│  grounded response│
│  with citations   │
└───────────────────┘
```

### Component Map
| Component | File | Role |
|---|---|---|
| TavilyService | `backend/services/tavily_service.py` (new) | Wraps Tavily Search API |
| Config | `backend/config.py` | Env vars & DEFAULT_CONFIG for Tavily |
| ConfigService | `backend/services/config_service.py` | Runtime config for search settings |
| StrandsAgentService | `backend/services/strands_agent.py` | Integrates search tool into prompt |
| ChatService | `backend/services/chat_service.py` | Passes search tool to agent flow |
| Chat route | `backend/routes/chat.py` | Streams tool_call events for search |

---

## Functional Requirements

1. A new `TavilyService` class provides a `search(query)` method that calls the Tavily Search API and returns structured results.
2. The agent decides whether to invoke web search based on:
   - Explicit user cues ("search for", "look up", "what's the latest", "current", "today").
   - LLM judgment — the system prompt instructs the model that it has a web search tool and when to use it.
3. When search is invoked, results are injected into the LLM prompt as grounding context before the model generates its final answer.
4. Search tool invocations appear in response `metadata.tool_calls` with:
   - `name: "web_search"`
   - `status: "success" | "error"`
   - `duration` (milliseconds)
   - `inputs: { query }` (the search query used)
   - `outputs: { result_count, sources: [{ title, url }] }` (summary, not full content)
5. The agent includes source citations in its response when using search results.
6. Search is disabled by default (`TAVILY_ENABLED=False`). When disabled, the agent behaves as today.
7. Search works with both Ollama and Gemini providers.

---

## Backend Requirements

### Configuration (`config.py`)

Add Tavily environment variables:

```python
# Tavily Web Search — API key is environment-only, never stored in config
TAVILY_ENABLED = os.getenv('TAVILY_ENABLED', 'False') == 'True'
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '')
TAVILY_SEARCH_DEPTH = os.getenv('TAVILY_SEARCH_DEPTH', 'basic')        # 'basic' | 'advanced'
TAVILY_MAX_RESULTS = int(os.getenv('TAVILY_MAX_RESULTS', '5'))
TAVILY_INCLUDE_ANSWER = os.getenv('TAVILY_INCLUDE_ANSWER', 'True') == 'True'
TAVILY_INCLUDE_DOMAINS = [
    d.strip() for d in os.getenv('TAVILY_INCLUDE_DOMAINS', '').split(',') if d.strip()
]
TAVILY_EXCLUDE_DOMAINS = [
    d.strip() for d in os.getenv('TAVILY_EXCLUDE_DOMAINS', '').split(',') if d.strip()
]
```

Add to `DEFAULT_CONFIG`:

```python
DEFAULT_CONFIG = {
    # ...existing keys...
    'tavily': {
        'enabled': TAVILY_ENABLED,
        'search_depth': TAVILY_SEARCH_DEPTH,
        'max_results': TAVILY_MAX_RESULTS,
        'include_answer': TAVILY_INCLUDE_ANSWER,
        'include_domains': TAVILY_INCLUDE_DOMAINS,
        'exclude_domains': TAVILY_EXCLUDE_DOMAINS,
    }
}
```

### New Service: `services/tavily_service.py`

```python
class TavilyService:
    """Client for the Tavily Search API."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, api_key: str = ''):
        config = config or {}
        self.enabled = bool(config.get('enabled', False))
        self.api_key = api_key or ''
        self.search_depth = config.get('search_depth', 'basic')
        self.max_results = int(config.get('max_results', 5))
        self.include_answer = bool(config.get('include_answer', True))
        self.include_domains = list(config.get('include_domains', []))
        self.exclude_domains = list(config.get('exclude_domains', []))
        self.base_url = 'https://api.tavily.com'
        self.timeout_seconds = int(config.get('timeout_seconds', 15))

    def is_available(self) -> bool:
        """Return True when Tavily is enabled and an API key is configured."""
        return bool(self.enabled and self.api_key)

    def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """Execute a search query against the Tavily API.

        Returns: {
            'answer': str | None,       # Tavily's direct answer (if include_answer)
            'results': [
                { 'title': str, 'url': str, 'content': str, 'score': float }
            ],
            'query': str,
            'response_time': float
        }
        Raises RuntimeError on API/network failure.
        """
```

- Uses `requests.post` to `https://api.tavily.com/search`.
- API key sent in request body (per Tavily API spec), never logged.
- Timeout defaults to 15 seconds.
- Returns structured results; raises `RuntimeError` on failure.

### Agent Integration (`strands_agent.py`)

Add a search-detection heuristic and prompt injection:

1. **`_wants_web_search(user_message: str) -> bool`**: Keyword/pattern heuristic similar to `_wants_visualization`:
   - Triggers on: "search for", "look up", "find out", "what's the latest", "current news", "today", "recent", "2025", "2026", references to real-time data.
   - Does NOT trigger on generic questions the model can answer from training data.

2. **`_web_search_instructions() -> str`**: System prompt addendum telling the model it has access to web search results and should cite sources.

3. **`_format_search_context(results: Dict) -> str`**: Formats Tavily results into a prompt-friendly context block:
   ```
   Web Search Results for "query":
   [1] Title — URL
   Content snippet...
   [2] Title — URL
   Content snippet...
   ```

4. **`_build_prompt`**: When search results are available, inject them as a `Context:` section before the user message.

### Chat Service Integration (`chat_service.py`)

1. Add `_build_tavily_service() -> TavilyService` (same pattern as `_build_gemini_service`).
2. In `process_message` and `stream_message`:
   - Build `TavilyService` from config.
   - If search is available and the message triggers search, invoke `tavily.search(query)`.
   - Time the search call; record a tool_call entry in metadata.
   - Pass search results to the agent/LLM for response generation.
   - On search failure, log the error and proceed without search (non-fatal).

3. Tool call metadata shape:
   ```python
   {
       'name': 'web_search',
       'status': 'success',       # or 'error'
       'duration_ms': 1234,
       'inputs': {'query': 'latest Python 3.13 features'},
       'outputs': {
           'result_count': 5,
           'sources': [
               {'title': 'What\'s New in Python 3.13', 'url': 'https://...'},
           ]
       }
   }
   ```

### New Endpoint: `GET /api/search/status`

Return whether web search is available (so the frontend can show an indicator).

```json
{
  "success": true,
  "data": {
    "available": true,
    "provider": "tavily",
    "search_depth": "basic",
    "max_results": 5
  }
}
```

### Docker Compose (`docker-compose.yml`)

Add Tavily env vars to the backend service:

```yaml
- TAVILY_ENABLED=${TAVILY_ENABLED:-False}
- TAVILY_API_KEY=${TAVILY_API_KEY:-}
- TAVILY_SEARCH_DEPTH=${TAVILY_SEARCH_DEPTH:-basic}
- TAVILY_MAX_RESULTS=${TAVILY_MAX_RESULTS:-5}
```

### `.env.example`

Add Tavily section:

```dotenv
# Tavily Web Search — API key is environment-only, never stored in config
TAVILY_ENABLED=False
TAVILY_API_KEY=
TAVILY_SEARCH_DEPTH=basic
TAVILY_MAX_RESULTS=5
TAVILY_INCLUDE_DOMAINS=
TAVILY_EXCLUDE_DOMAINS=
```

---

## Frontend Requirements

### Minimal Phase 1

Frontend changes are minimal — the tool activity is surfaced through the existing `tool_calls` metadata and the planned agent-activity-tool-usage-indicators spec.

1. **Search status indicator** (optional): Show a small icon/badge in the chat header or config panel indicating web search is available (via `GET /api/search/status`).
2. **Tool activity rendering**: When `metadata.tool_calls` contains a `web_search` entry, render it according to the patterns defined in `agent-activity-tool-usage-indicators.spec.md`:
   - Tool name: "Web Search"
   - Input summary: the search query
   - Output summary: result count + source list
   - Duration badge
3. **Source citations**: If the agent response includes source URLs, render them as clickable links.

### Config Panel (Phase 2)

A future enhancement could add a "Tools" section to the config panel allowing the user to:
- Toggle web search on/off.
- Adjust `search_depth` and `max_results`.
- Configure domain include/exclude lists.

This is out of scope for Phase 1.

---

## Security / Validation Considerations

- `TAVILY_API_KEY` is environment-only — never stored in `DEFAULT_CONFIG`, never returned by any API endpoint, never logged.
- Search queries are sanitized (trimmed, length-capped at 400 characters) before sending to Tavily.
- Tavily responses are treated as untrusted external input — content is sanitized before injection into prompts (strip control characters, cap content length per result).
- Domain include/exclude lists are validated as valid domain patterns.
- Search timeout (15s default) prevents the agent from hanging on slow Tavily responses.
- All Tavily requests use HTTPS.
- Search failure is non-fatal — the agent continues without search results and does not expose the error to the user beyond the tool_call status.

---

## Edge Cases

1. **Tavily API key missing/invalid** → `is_available()` returns false; search silently skipped; agent responds from LLM knowledge only.
2. **Tavily rate limit (429)** → `search()` raises RuntimeError; caught in chat service; tool_call logged with `status: "error"`; agent responds without search.
3. **Tavily returns no results** → Empty results passed to agent; model informed "no relevant results found"; agent answers from its own knowledge.
4. **Search timeout** → Treated as error; agent proceeds without search to avoid blocking the response.
5. **Very long search results** → Content per result is truncated (e.g., 500 chars) to stay within prompt limits; total injected context capped at `context_max_input_chars`.
6. **User asks about something the model can answer without search** → Heuristic does not trigger; no unnecessary API calls.
7. **Provider is Gemini** → Search works identically; results are injected into the Gemini prompt the same way.
8. **Concurrent requests** → Each request builds its own `TavilyService` instance; no shared mutable state.

---

## Testing Requirements

### Backend Unit Tests

1. **`TavilyService`**:
   - `is_available()` returns `True` only when enabled and API key present.
   - `search()` sends correct payload to Tavily API (mock `requests.post`).
   - `search()` handles timeout, HTTP errors, malformed responses gracefully.
   - `search()` respects `max_results`, `search_depth`, `include_domains`, `exclude_domains`.
   - Query is sanitized (trimmed, length-capped).

2. **`StrandsAgentService`**:
   - `_wants_web_search()` triggers on expected keywords and not on generic questions.
   - `_format_search_context()` produces well-structured context from Tavily results.
   - `_build_prompt()` injects search context when results are provided.

3. **`ChatService`**:
   - When Tavily is available and message triggers search, `search()` is called and results are passed to agent.
   - When Tavily is unavailable, search is skipped entirely.
   - Search failure does not crash the request; tool_call logged with error status.
   - Tool call metadata has correct shape (`name`, `status`, `duration_ms`, `inputs`, `outputs`).

4. **`ConfigService`**:
   - `tavily` config section is present in default config.
   - Config updates do not expose or accept `TAVILY_API_KEY`.

### Frontend Unit Tests

1. Tool call with `name: "web_search"` renders correctly in message metadata.
2. Source URLs in agent responses are rendered as clickable links.

---

## Acceptance Criteria

1. When `TAVILY_ENABLED=True` and `TAVILY_API_KEY` is set, the agent can perform web searches.
2. Asking "What's the latest news about [topic]?" returns a response grounded in current web data with source citations.
3. Search tool invocations appear in `metadata.tool_calls` with query, result count, sources, and duration.
4. When Tavily is disabled or unavailable, the agent works exactly as before with no errors.
5. The Tavily API key is never exposed in config endpoints, logs, or frontend.
6. Search failures are non-fatal — the agent responds from LLM knowledge and logs the error.
7. All backend tests pass.

---

## Phase 2 Considerations

- **Config panel UI**: Tools section to toggle search and adjust parameters.
- **Search result caching**: Cache recent searches (by query hash) in Redis/SQLite to reduce API calls and latency.
- **Advanced search**: Use Tavily's `advanced` search depth for complex queries.
- **Tavily Extract**: Use the Extract endpoint to fetch full page content for specific URLs.
- **Multi-provider search**: Swap in SerpAPI, Brave Search, or other providers via the same tool interface.
- **User-triggered search**: Allow users to explicitly request "search for X" via a chat command or button.
- **Search budget / rate limiting**: Track API usage and enforce per-user or global limits.
- **Citation rendering**: Rich citation cards with favicons, titles, and snippets inline in the chat.
