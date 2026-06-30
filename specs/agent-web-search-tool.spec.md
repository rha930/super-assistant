# Spec: Agent Web Search Tool

## Purpose
Give the agent the ability to search the web for current information so it can answer questions that require up-to-date data beyond its training cutoff or local knowledge base.

## Problem Statement
The agent can only respond using its training data and conversation history. It cannot answer questions about current events, recent documentation, live data, or anything that requires real-time information from the internet.

## Goals
- Provide the agent with a web search tool that retrieves relevant results for a user query.
- Inject search results into the agent's prompt context so responses are grounded in current web data.
- Support configurable search provider (default: DuckDuckGo — no API key required).
- Allow the agent to decide when a search is needed rather than searching on every message.
- Display source citations in agent responses so users can verify information.

## Non-Goals
- No full web page scraping or crawling.
- No browser automation or JavaScript rendering.
- No caching or indexing of past search results.
- No user-facing search UI — search is exclusively an agent-invoked tool.

---

## User Stories
- As a user, I can ask the agent questions about current events and receive answers with web sources.
- As a user, I can see which web sources the agent used in its response.
- As a user, I can enable or disable the web search tool from the configuration panel.
- As a user, the agent only searches the web when my question warrants it — not on every message.

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
┌─────────────────┐     ┌──────────────────────┐
│  Agent Service   │────▶│  Web Search Tool      │
│  (Ollama LLM)   │     │  (Search Provider)    │
└────────┬────────┘     └──────────┬───────────┘
         │                         │
         │  ◀── search results ────┘
         │       injected as context
         ▼
┌─────────────────┐
│  Agent Response  │
│  (with citations)│
└─────────────────┘
```

### Tool Invocation Strategy
The agent does **not** call tools natively (Ollama generate mode). The tool layer uses **pre-prompt intent detection** to decide whether to invoke the search tool before the LLM call:

1. Chat service receives user message.
2. Intent detector evaluates whether the message needs web search.
3. If yes: call search provider → format results → inject as context in prompt.
4. Agent generates response with search context available.
5. Response metadata includes sources used.

---

## Backend Requirements

### New Service: `WebSearchService`

**Location:** `backend/services/web_search_service.py`

```python
class WebSearchService:
    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]
    def is_available(self) -> bool
```

**`WebSearchResult` model:**
```python
@dataclass
class WebSearchResult:
    title: str
    url: str
    snippet: str
```

### Search Provider: DuckDuckGo

**Default provider** — uses the `duckduckgo-search` Python package (no API key needed).

| Aspect | Detail |
|--------|--------|
| Package | `duckduckgo-search>=7.0.0` |
| Method | `DDGS().text(query, max_results=N)` |
| Rate limiting | Built-in; add configurable delay between calls |
| Timeout | 10 seconds per search |
| Fallback | Return empty results on failure; do not block agent response |

### Intent Detection

**Location:** Add method to `StrandsAgentService` or a standalone utility.

**`_needs_web_search(message: str) -> bool`**

Heuristic keyword/pattern detection (similar to existing `_wants_visualization()`):

**Triggers (should search):**
- Temporal keywords: "latest", "recent", "current", "today", "this week", "2025", "2026"
- Lookup patterns: "what is the price of", "who won", "what happened", "news about"
- Explicit requests: "search for", "look up", "find online", "google"
- Factual questions about named entities likely to have changed: people, companies, events

**Exclusions (should NOT search):**
- Code generation requests: "write a function", "create a class", "fix this code"
- Math/logic: "calculate", "solve", "what is 2+2"
- Conversational: greetings, thanks, follow-ups without new factual questions
- Questions the model can confidently answer from training data (general knowledge)

### Context Injection Format

Search results are injected into the prompt before the user message:

```
[Web Search Results]
The following are recent web search results relevant to the user's question.
Use these to inform your response. Cite sources using [Source Title](URL) format.

1. **{title}**
   {snippet}
   Source: {url}

2. **{title}**
   {snippet}
   Source: {url}

---
```

### New Endpoint

**`GET /api/tools/web-search/status`**

Returns whether the web search tool is enabled and available.

```json
{
  "success": true,
  "data": {
    "enabled": true,
    "provider": "duckduckgo",
    "available": true
  }
}
```

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `WEB_SEARCH_ENABLED` | `True` | Master toggle for web search tool |
| `WEB_SEARCH_PROVIDER` | `duckduckgo` | Search provider (only duckduckgo for now) |
| `WEB_SEARCH_MAX_RESULTS` | `5` | Max results to retrieve per search |
| `WEB_SEARCH_TIMEOUT` | `10` | Timeout in seconds for search requests |

Add to `backend/config.py` and expose in `DEFAULT_CONFIG` under a `tools` key:

```python
DEFAULT_CONFIG = {
    ...
    'tools': {
        'web_search': {
            'enabled': True,
            'max_results': 5
        }
    }
}
```

### Integration with Chat Service

Modify `chat_service.py` flow:

```python
# In process_message() and stream_message(), before agent invocation:

search_context = ''
if web_search_enabled and web_search_service.is_available():
    if agent._needs_web_search(message):
        results = web_search_service.search(message, max_results=config['tools']['web_search']['max_results'])
        if results:
            search_context = format_search_context(results)
            metadata['tool_calls'].append({
                'tool': 'web_search',
                'query': message,
                'result_count': len(results),
                'sources': [{'title': r.title, 'url': r.url} for r in results]
            })

# Pass search_context to agent for prompt injection
agent.invoke_agent(..., tool_context=search_context)
```

### Agent Service Changes

Update `StrandsAgentService._build_prompt()` to accept and include tool context:

```python
def _build_prompt(self, system_prompt, conversation_history, user_message, tool_context=''):
    prompt = f"System: {system_prompt}\n\n"
    if tool_context:
        prompt += f"{tool_context}\n\n"
    # ... existing history + user message logic
```

---

## Frontend Requirements

### Config Panel: Tool Settings

Add a **Tools** section to `ConfigPanel.vue` below Agent Settings:

```
── Tools ──────────────────────────
  Web Search
  [✓] Enable web search          (toggle)
  Max results: [5]               (number input, 1-10)
───────────────────────────────────
```

- Toggle maps to `config.tools.web_search.enabled`
- Max results maps to `config.tools.web_search.max_results`
- Persisted via existing config save flow

### Config Store

Extend the `Config` interface:

```typescript
interface Config {
  // ... existing fields
  tools: {
    web_search: {
      enabled: boolean
      max_results: number
    }
  }
}
```

### Message Display: Source Citations

When `metadata.tool_calls` contains a `web_search` entry with `sources`, render a collapsible sources section below the agent message:

```
Agent response text here...

▸ Sources (3)
  • Source Title — example.com
  • Source Title — example.com
  • Source Title — example.com
```

- Sources are rendered as clickable links opening in new tab.
- Section is collapsed by default; click to expand.
- Only shown when sources are present in metadata.

---

## Data & State Requirements

- `tools.web_search` config is persisted backend-side via existing config endpoint.
- Search results are **not** persisted — they exist only in the response metadata for the current message.
- `tool_calls` array in message metadata is persisted in chat history for display on reload.

---

## Edge Cases

1. **Search provider unreachable:**
   - Log warning, return empty results, proceed with normal agent response.
   - Do not surface error to user — search is best-effort.

2. **Rate limiting from search provider:**
   - Catch rate-limit errors, return empty results.
   - Consider adding a minimum interval between searches (e.g., 2 seconds).

3. **Search returns irrelevant results:**
   - Agent sees results as context but is not forced to use them.
   - System prompt should instruct: "Use search results only if relevant."

4. **Very long search snippets:**
   - Truncate each snippet to 300 characters.
   - Total injected context should not exceed 3000 characters.

5. **User explicitly says "don't search":**
   - Intent detector should respect explicit opt-out phrases.

6. **Concurrent searches:**
   - Each request is independent; no shared state between searches.

---

## Security & Validation

- Sanitize search query before sending to provider (strip control characters, limit to 200 chars).
- Treat all search result content as untrusted — render as plain text in UI, never as raw HTML.
- URLs from search results should be rendered as links but never auto-loaded or embedded.
- Do not log full search result content (may contain sensitive external data); log only query and result count.

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `duckduckgo-search` | `>=7.0.0` | Web search provider |

Add to `backend/requirements.txt`.

---

## Acceptance Criteria

1. Agent answers current-events questions using web search results with source citations.
2. Agent does NOT search on every message — only when intent detection triggers.
3. Web search can be toggled on/off from the configuration panel.
4. Search failures do not crash the agent or block responses.
5. Sources are displayed below agent messages and link to original pages.
6. Configuration (enabled, max_results) persists across sessions.

---

## Test Cases

### Unit Tests
- `_needs_web_search()` returns `True` for temporal/lookup queries.
- `_needs_web_search()` returns `False` for code/math/conversational queries.
- `WebSearchService.search()` returns structured results from mock provider.
- `WebSearchService.search()` returns empty list on provider error.
- Search context formatting produces expected prompt injection string.
- Query sanitization strips control characters and enforces length limit.

### Integration Tests
- Search results are injected into agent prompt and appear in response metadata.
- `tool_calls` in message metadata persists in chat history.
- Config toggle disables search (no `tool_calls` in response when off).
- `GET /api/tools/web-search/status` returns correct enabled/available state.

### E2E Tests
- Ask "What happened in the news today?" → response includes sources section.
- Ask "Write a Python function to sort a list" → no web search triggered.
- Disable web search in config → current-events question returns generic answer without sources.

---

## Implementation Notes

- Place `WebSearchService` in `backend/services/web_search_service.py`.
- Place `WebSearchResult` model in `backend/models/web_search.py`.
- Add `_needs_web_search()` to `StrandsAgentService` alongside existing `_wants_visualization()`.
- Add tool status endpoint to a new `backend/routes/tools.py` blueprint or to existing `health.py`.
- Frontend sources display can reuse the collapsible pattern from graph artifacts.
- The `tool_context` parameter approach keeps the agent service clean — no direct tool coupling.
