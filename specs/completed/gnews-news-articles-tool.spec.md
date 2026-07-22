# Spec: GNews News Articles Tool for Agent

## Purpose
Give the agent a news search tool powered by the [GNews API](https://gnews.io/) so it can retrieve recent news articles on any topic and incorporate them into responses.

## Problem Statement
The agent has no access to live news content. Users asking about recent events, breaking stories, or current developments receive responses based only on training data. A GNews tool closes this gap by letting the agent fetch real news articles on demand, providing grounded, up-to-date answers with source attribution.

## Goals
- Provide a `GNewsService` that wraps the GNews REST API and can be invoked as an agent tool.
- The agent automatically decides when a query benefits from news lookup (e.g., "what's happening with…", "latest news on…", "recent articles about…").
- Inject retrieved articles into the LLM prompt context so the response is grounded in real news.
- Surface tool usage in response metadata (`tool_calls`) so the activity indicator can render it.
- Keep the service modular — the news provider can be swapped without changing the agent interface.
- Support both Ollama and Gemini providers as the primary LLM.

## Non-Goals
- No full article body retrieval in Phase 1 — GNews returns titles, descriptions, and URLs only.
- No caching of results in Phase 1.
- No user-facing news UI (the agent decides when to search; users do not trigger it manually).
- No image/media handling.
- No cost management or quota tracking UI.
- No GNews `/headlines` or `/topics` endpoints in Phase 1 — query search only.

---

## User Stories
- As a user, I can ask the agent about recent news and get an answer grounded in real articles.
- As a user, I can see when the agent fetched news articles (tool activity indicator).
- As a user, I can see the article titles and sources the agent used.
- As an admin, I can enable/disable the news tool and provide a GNews API key via environment variables.
- As an admin, I can configure the max number of results and language/country filters.

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
         │  Agent detects request for recent news
         ▼
┌───────────────────┐       ┌──────────────────┐
│  News Decision    │──────▶│  GNewsService     │
│  (heuristic /     │       │  (REST API call)  │
│   LLM judgment)   │       └────────┬─────────┘
└───────────────────┘                │
         │◀──────── article results ─┘
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
| GNewsService | `backend/services/gnews_service.py` (new) | Wraps GNews search API |
| Config | `backend/config.py` | Env vars & DEFAULT_CONFIG for GNews |
| StrandsAgentService | `backend/services/strands_agent.py` | Injects news tool into prompt |
| ChatService | `backend/services/chat_service.py` | Constructs GNewsService; passes results to agent |
| Chat route | `backend/routes/chat.py` | Streams `tool_call` events for news fetch |

---

## Functional Requirements

1. A new `GNewsService` class exposes a `search(query)` method that calls the GNews `/search` endpoint and returns structured article data.
2. The agent decides whether to invoke the news tool based on:
   - Explicit user cues: "latest news", "recent articles", "what's happening with", "today's news", "news about".
   - LLM judgment — the system prompt informs the model it has a news tool and when to use it.
3. When the news tool is invoked, retrieved articles are injected into the LLM prompt as grounding context before the model generates its final answer.
4. News tool invocations appear in `metadata.tool_calls` with:
   - `name: "news_search"`
   - `status: "success" | "error"`
   - `duration` (milliseconds)
   - `inputs: { query }` — the search query used
   - `outputs: { article_count, articles: [{ title, source, url, published_at }] }` — summary only, not full content
5. The agent includes article titles and source names as citations in its response when news results are used.
6. The news tool is disabled by default (`GNEWS_ENABLED=False`). When disabled the agent behaves as today.
7. The tool works with both Ollama and Gemini providers.

---

## Backend Requirements

### Configuration (`backend/config.py`)

Add GNews environment variables (API key is environment-only — never stored in `DEFAULT_CONFIG`):

```python
# GNews News Articles Tool — API key is environment-only
GNEWS_ENABLED = os.getenv('GNEWS_ENABLED', 'False') == 'True'
GNEWS_API_KEY = os.getenv('GNEWS_API_KEY', '')
GNEWS_MAX_RESULTS = int(os.getenv('GNEWS_MAX_RESULTS', '5'))   # GNews free tier max: 10
GNEWS_LANGUAGE = os.getenv('GNEWS_LANGUAGE', 'en')
GNEWS_COUNTRY = os.getenv('GNEWS_COUNTRY', 'us')
GNEWS_TIMEOUT_SECONDS = int(os.getenv('GNEWS_TIMEOUT_SECONDS', '10'))
```

Add to `DEFAULT_CONFIG`:

```python
'gnews': {
    'enabled': GNEWS_ENABLED,
    'max_results': GNEWS_MAX_RESULTS,
    'language': GNEWS_LANGUAGE,
    'country': GNEWS_COUNTRY,
    'timeout_seconds': GNEWS_TIMEOUT_SECONDS,
    # GNEWS_API_KEY is never stored here — read from env at runtime only
},
```

### GNews Service (`backend/services/gnews_service.py`)

```python
class GNewsService:
    BASE_URL = 'https://gnews.io/api/v4'

    def __init__(self, config: dict, api_key: str = ''):
        self.enabled: bool
        self.api_key: str        # never logged or exposed
        self.max_results: int
        self.language: str
        self.country: str
        self.timeout_seconds: int

    def is_available(self) -> bool:
        """Return True when enabled and api_key is set."""

    def search(self, query: str) -> dict:
        """
        Call GET /search?q=<query>&max=<n>&lang=<l>&country=<c>&token=<key>
        Return:
        {
            'articles': [
                {
                    'title': str,
                    'description': str,
                    'url': str,
                    'source': str,
                    'published_at': str,   # ISO 8601
                }
            ],
            'total_articles': int
        }
        Raise RuntimeError on API/network failure.
        """
```

- The `api_key` is passed as the `token` query parameter over HTTPS (GNews requirement).
- Never log the API key or include it in error messages.
- Validate that `query` is a non-empty string before making the request.
- On non-200 HTTP status, raise `RuntimeError` with the status code (not the key).

### Agent Integration (`backend/services/strands_agent.py`)

- Add a `_wants_news(user_message: str) -> bool` heuristic (similar to `_wants_visualization`).
  - Trigger keywords: `latest news`, `recent news`, `news about`, `what's happening`, `breaking`, `today's news`, `news on`, `news for`, `current events`.
- Add `_news_context_instructions() -> str` to inject into the system prompt when news results are available.
- In `_build_prompt`, when the GNewsService is available and `_wants_news` is True:
  1. Call `gnews_service.search(user_message)` (or a cleaned sub-query).
  2. Format results as a numbered article list.
  3. Append as a `Context:` section in the prompt.
  4. Record the tool call in `metadata.tool_calls`.

`GNewsService` is constructed in `ChatService` and passed to `StrandsAgentService` (or injected per-request) so the agent layer stays decoupled from config details.

### ChatService (`backend/services/chat_service.py`)

- Import `GNEWS_API_KEY` from `config`.
- Construct `GNewsService` from `self.config.get('gnews', {})` and the env API key.
- Pass the service instance to the agent when generating a response (mirroring the Gemini pattern).

---

## Security / Validation

- `GNEWS_API_KEY` is read from the environment only. It is never stored in `DEFAULT_CONFIG`, never returned from any endpoint, and never logged.
- The `query` parameter is passed directly to the GNews API as a URL query parameter; no shell execution or SQL is involved. Validate it is a non-empty string ≤ 500 characters before making the request.
- HTTPS is enforced by the GNews base URL (`https://gnews.io`).
- Any HTTP error response from GNews is raised as a `RuntimeError` with the status code only — API key and response body are not surfaced to callers or logs.

---

## Testing Requirements

- Unit tests in `backend/tests/test_gnews_service.py`:
  - `GNewsService.is_available()` returns `False` when disabled or when `api_key` is empty.
  - `GNewsService.search()` raises `RuntimeError` when not available.
  - `GNewsService.search()` returns correctly shaped article dicts on a mocked HTTP 200 response.
  - `GNewsService.search()` raises `RuntimeError` on HTTP 4xx/5xx responses (API key is not leaked in the error message).
  - `GNewsService.search()` raises `RuntimeError` on connection timeout.
  - Empty or whitespace-only `query` raises `ValueError` before any HTTP call.

- Integration smoke test: confirm `ChatService` builds a `GNewsService` from config without error when `GNEWS_ENABLED=False`.

---

## Acceptance Criteria

- [ ] `GNewsService` is implemented with `is_available()` and `search(query)` methods.
- [ ] Config vars (`GNEWS_ENABLED`, `GNEWS_API_KEY`, `GNEWS_MAX_RESULTS`, `GNEWS_LANGUAGE`, `GNEWS_COUNTRY`, `GNEWS_TIMEOUT_SECONDS`) are read from environment in `config.py`.
- [ ] `DEFAULT_CONFIG` in `config.py` includes a `gnews` section (no API key).
- [ ] When `GNEWS_ENABLED=False` or no API key, the agent behaves as today with no errors.
- [ ] When enabled, the agent appends news context to the prompt for news-related queries.
- [ ] Tool calls appear in `metadata.tool_calls` with the shape defined in Functional Requirement 4.
- [ ] The API key is never logged, returned from an endpoint, or stored in config.
- [ ] All unit tests in `test_gnews_service.py` pass.
- [ ] Backend test suite (`pytest`) remains green.

---

## Phase 2 Considerations

- GNews `/headlines` endpoint for unprompted headline summaries.
- `/topics` endpoint support (e.g., `technology`, `sports`, `health`).
- Result caching (e.g., TTL-based in Redis) to reduce API quota consumption.
- User-facing toggle in the Config Panel to enable/disable the news tool at runtime.
- Configurable include/exclude source domains.
- Full article body retrieval via a secondary fetch with content parsing.
