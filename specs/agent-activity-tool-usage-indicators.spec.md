# Spec: Agent Activity & Tool Usage Indicators in Chat

## Purpose
Surface real-time agent activity — especially tool invocations — in the chat window so users can see what the agent is doing, not just the final text response.

## Problem Statement
The chat currently shows a single generic "thinking" indicator (e.g., "Analyzing context…", "Drafting response…") that cycles through hardcoded phases unrelated to actual agent behavior. When the agent uses tools (web search, knowledge base, graph generation), the user has no visibility into those actions. The `tool_calls` metadata is captured but only rendered as a minimal count badge ("Tool calls: 2") on the final message — no tool names, inputs, outputs, or timing are shown.

## Goals
- Show live, contextual status updates that reflect what the agent is actually doing (e.g., "Searching the web…", "Querying knowledge base…").
- Display a collapsible tool activity log within each agent message showing tool name, status, duration, and summary.
- Emit tool usage events from the backend stream so the frontend can render them in real time.
- Keep the UI non-intrusive — tool details should be collapsed by default and expandable on demand.

## Non-Goals
- No editing or re-running of tool calls from the UI.
- No full tool input/output dump (security/size concern) — show summaries only.
- No agent step-debugging or breakpoints.
- No changes to which tools the agent has access to.

---

## User Stories
- As a user, I can see a live status label that updates to reflect the agent's current action (e.g., "Searching the web for…").
- As a user, I can see a tool activity section in the agent's message after it completes, showing which tools were used.
- As a user, I can expand a tool call to see its name, a brief input summary, result summary, and how long it took.
- As a user, I can tell at a glance whether a tool succeeded or failed via an icon/color indicator.

---

## Architecture

### Streaming Event Extension

Currently the backend emits these SSE event shapes:
```json
{ "chunk": "...", "done": false, "thinking": "Drafting response..." }
{ "chunk": "", "done": true, "metadata": { "tool_calls": [...] } }
```

This spec adds a new `tool_event` field to the stream:
```json
{
  "chunk": "",
  "done": false,
  "thinking": "Searching the web...",
  "tool_event": {
    "id": "tool_1719700000_websearch",
    "name": "web_search",
    "status": "started",
    "display_name": "Web Search",
    "input_summary": "query: 'kubernetes pod health check'",
    "timestamp": "2026-07-01T12:00:00Z"
  }
}
```

When the tool completes:
```json
{
  "chunk": "",
  "done": false,
  "thinking": "Processing search results...",
  "tool_event": {
    "id": "tool_1719700000_websearch",
    "name": "web_search",
    "status": "completed",
    "display_name": "Web Search",
    "output_summary": "Found 3 relevant results",
    "duration_ms": 1230,
    "timestamp": "2026-07-01T12:00:01.230Z"
  }
}
```

Tool event statuses: `started`, `completed`, `failed`.

---

## Backend Requirements

### 1. Tool Event Emission in Streaming

Modify the streaming path in `services/chat_service.py` and `routes/chat.py` to emit `tool_event` payloads when tools are invoked.

Each tool service (graph artifact, knowledge base, web search, etc.) should yield or callback a tool event at start and completion:

```python
# Tool event schema
{
    "id": str,              # Unique ID for this invocation
    "name": str,            # Internal tool name (e.g., "web_search")
    "status": str,          # "started" | "completed" | "failed"
    "display_name": str,    # Human-friendly label (e.g., "Web Search")
    "input_summary": str,   # Truncated/sanitized input description (optional)
    "output_summary": str,  # Truncated/sanitized result description (optional, on completion)
    "duration_ms": int,     # Elapsed time (optional, on completion)
    "error": str,           # Error message (optional, on failure)
    "timestamp": str        # ISO 8601
}
```

### 2. Thinking Text Derived from Tool Events

Replace the hardcoded chunk-count-based thinking text in `routes/chat.py` with context-aware labels:

| Agent State | Thinking Text |
|---|---|
| Before first chunk | `Reviewing your request...` |
| Tool started: `web_search` | `Searching the web...` |
| Tool started: `knowledge_base_search` | `Searching knowledge base...` |
| Tool started: `graph_generation` | `Generating visualization...` |
| Tool completed (any) | `Processing results...` |
| Generating text (chunks flowing) | `Writing response...` |
| Final event | `Done.` |

### 3. Tool Metadata on Final Message

The final `done: true` event should include the full list of tool events in `metadata.tool_calls`, replacing the current empty array:

```json
{
  "done": true,
  "metadata": {
    "tool_calls": [
      {
        "id": "tool_1719700000_websearch",
        "name": "web_search",
        "display_name": "Web Search",
        "status": "completed",
        "input_summary": "query: 'kubernetes pod health check'",
        "output_summary": "Found 3 relevant results",
        "duration_ms": 1230
      }
    ]
  }
}
```

---

## Frontend Requirements

### 1. Type Updates (`types/message.ts`)

Extend the `tool_calls` type in the `Message` metadata:

```typescript
interface ToolCall {
  id: string
  name: string
  display_name: string
  status: 'started' | 'completed' | 'failed'
  input_summary?: string
  output_summary?: string
  duration_ms?: number
  error?: string
}

export interface Message {
  // ... existing fields
  metadata: {
    tokens_used?: number
    tool_calls?: ToolCall[]
    reasoning?: string
  }
}
```

### 2. Stream Handler Updates (`stores/chatStore.ts`)

When a `tool_event` payload arrives in the SSE stream:
- If `status === 'started'`: append to the in-progress message's `metadata.tool_calls` array.
- If `status === 'completed'` or `'failed'`: update the matching entry by `id` with output, duration, and final status.
- Update `uiStore.thinkingText` with the `thinking` value from the event.

### 3. Tool Activity Component (`components/ToolActivity.vue`)

A new component rendered inside `Message.vue` for agent messages that have tool calls:

**Collapsed state (default):**
```
🔧 3 tools used  ▸
```

**Expanded state:**
```
🔧 3 tools used  ▾
┌──────────────────────────────────────────┐
│ ✅ Web Search                    1.2s    │
│    query: 'kubernetes pod health check'  │
│    Found 3 relevant results              │
├──────────────────────────────────────────┤
│ ✅ Knowledge Base Search         0.3s    │
│    query: 'pod restart runbook'          │
│    2 matching documents                  │
├──────────────────────────────────────────┤
│ ❌ Graph Generation              0.8s    │
│    Error: insufficient data points       │
└──────────────────────────────────────────┘
```

**Design details:**
- Status icons: `✅` completed, `❌` failed, `⏳` in-progress (animated spinner).
- Duration right-aligned.
- Input/output summaries shown as muted secondary text.
- Respects current theme (light/dark).
- Smooth expand/collapse animation (CSS transition on max-height).

### 4. Live Tool Indicator in Thinking State

While the agent is actively using a tool (between `started` and `completed` events), show the tool name in the thinking indicator:

```
⏳ Searching the web...
```

Replace the current generic pulsing text with the `thinking` value from the stream event, which now reflects actual tool usage.

### 5. Message Component Updates (`components/Message.vue`)

- Replace the existing `Tool calls: N` badge with the `ToolActivity` component.
- Only render `ToolActivity` when `message.metadata.tool_calls` is non-empty.
- Position below the message content, above any timestamp/footer.

---

## Security & Validation

- **Input summaries must be truncated** to a maximum of 200 characters to prevent leaking large payloads.
- **Output summaries must be sanitized** — no raw HTML, no credentials, no PII.
- **Tool names must be whitelisted** — only emit events for registered tools; ignore unknown tool names.
- **Fail open** — if tool event emission fails, the stream must continue without the event. Tool events are informational, not critical path.

---

## Testing Requirements

### Backend
1. **Unit test**: Tool event emission produces correct schema (`id`, `name`, `status`, `timestamp`).
2. **Unit test**: Thinking text updates correctly based on tool events.
3. **Integration test**: Streaming endpoint emits `tool_event` payloads between chunk events when a tool is invoked.
4. **Edge case**: Tool failure emits a `failed` event with error summary, stream continues.

### Frontend
1. **Unit test**: `ToolActivity.vue` renders correct count, icons, and labels for completed/failed tools.
2. **Unit test**: Expand/collapse toggles visibility of tool details.
3. **Unit test**: `chatStore` correctly appends and updates tool calls from stream events.
4. **Integration test**: End-to-end stream with tool events renders live indicator and final tool activity section.

---

## Phase 2 Considerations

- **Tool call input/output viewer**: Full (redacted) input/output in a modal for debugging.
- **Tool execution timeline**: Gantt-style visualization showing parallel/sequential tool execution.
- **Tool retry from UI**: Allow users to re-run a failed tool call.
- **Tool usage analytics**: Track tool call frequency, duration, and failure rates across conversations.
- **Streaming tool output**: Show partial tool results as they arrive (e.g., search results appearing one by one).
