# Spec: Agent Activity & Tool Usage Indicators in Chat

## Purpose
Surface real-time agent activity — especially tool invocations — in the chat window so users can see what the agent is doing, not just the final text response.

## Problem Statement
The chat currently shows a single generic "thinking" indicator (e.g., "Analyzing context…", "Drafting response…") that cycles through hardcoded phases unrelated to actual agent behavior. When the agent uses tools (web search, knowledge base, graph generation), the user has no visibility into those actions. The `tool_calls` metadata is captured but only rendered as a minimal count badge ("Tool calls: 2") on the final message — no tool names, inputs, outputs, timing, or **ordered sequence of steps** are shown. When the agent runs several tools in one turn, the user cannot see which tools ran or in what order.

---

## Implementation Status (2026-08)

A first slice has shipped: the streaming path now surfaces live tool usage and
every response carries an **ordered** `tool_calls` list. The richer per-tool
activity log, the ordered step trail, and the dedicated `ToolActivity.vue`
component are still outstanding.

**Implemented**
- Streaming callback in [chat_service.py](../backend/services/chat_service.py)
  (`stream_message._cb`) emits a running, **ordered** `tool_calls` list in each
  SSE event's `metadata.tool_calls`, and a `thinking: "Using <tool>..."` label
  when a tool starts. On the final `result` event every entry is flipped to
  `status: "success"`.
- Sync path (`process_message`) collects the same ordered `tool_calls` via the
  agent callback and returns them in `metadata.tool_calls`.
- `database_query` records a **detailed** activity record
  (`{name, status, duration, inputs, outputs}`, counts only) through an
  `activity_sink`; `_merge_db_activity` merges these into `tool_calls` in call
  order (see [strands_tools.py](../backend/services/strands_tools.py) and
  [chat_service.py](../backend/services/chat_service.py)).
- Frontend consumes `payload.thinking`
  ([uiStore.ts](../frontend/src/stores/uiStore.ts) → `setThinking`) and shows it
  with a pulsing label in [ChatWindow.vue](../frontend/src/components/ChatWindow.vue).
- [Message.vue](../frontend/src/components/Message.vue) renders a minimal
  `Tool calls: N` badge from `metadata.tool_calls`.

**Remaining**
- Ordered, expandable **step trail** in the message showing each tool the agent
  ran, in sequence (the focus of this update — see "Multi-Tool Step Sequence").
- `ToolActivity.vue` component and the richer per-tool row (icon, duration,
  input/output summary).
- Consistent enrichment (`display_name`, `input_summary`, `output_summary`,
  `duration_ms`) for **all** tools, not just `database_query`.
- Context-aware thinking labels beyond the generic `Using <tool>...`.
- Rich `ToolCall` typing in `types/message.ts` (currently `{ name?, input? }`).

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
- As a user, when the agent runs several tools in one turn, I can see the **ordered steps** it took (step 1, step 2, …) and how many times each tool ran.
- As a user, I can expand a tool call to see its name, a brief input summary, result summary, and how long it took.
- As a user, I can tell at a glance whether a tool succeeded or failed via an icon/color indicator.

---

## Architecture

### Streaming Events (as implemented)

The streaming path ([chat_service.py](../backend/services/chat_service.py) →
`stream_message`) drives a callback that pushes events onto a queue. Each SSE
event already carries an **ordered** `tool_calls` list under `metadata`, so the
frontend can reconstruct the exact sequence of tools the agent used.

Text chunk event:
```json
{ "chunk": "...", "done": false,
  "metadata": { "tool_calls": [ { "name": "web_search", "status": "in_progress" } ] } }
```

Tool-start event (a new tool was invoked):
```json
{ "chunk": "", "done": false, "thinking": "Using web_search...",
  "metadata": { "tool_calls": [ { "name": "web_search", "status": "in_progress" } ] } }
```

Final event (all steps resolved, in call order):
```json
{ "chunk": "", "done": true,
  "metadata": {
    "tool_calls": [
      { "name": "web_search", "status": "success" },
      { "name": "database_query", "status": "success",
        "duration": 1230, "inputs": { "connector_name": "sample", "sql": "..." },
        "outputs": { "row_count": 3, "truncated": false } }
    ],
    "artifacts": [ ... ], "provider": "ollama", "model": "..." } }
```

Notes vs. the original design:
- Instead of a separate `tool_event` object, the running list lives in
  `metadata.tool_calls` and grows in **call order** as tools fire.
- Statuses used today are `in_progress` and `success` (plus `error` for
  `database_query`). The original `started`/`completed`/`failed` naming is the
  target for the enrichment step below.
- Only `database_query` currently carries `duration`/`inputs`/`outputs`; other
  tools carry `{name, status}` only.

### Target enrichment (delta)

To power the full activity log, each tool invocation should converge on:
```json
{ "id": "str", "name": "str", "display_name": "str",
  "status": "started | completed | failed",
  "input_summary": "str", "output_summary": "str",
  "duration_ms": 0, "error": "str" }
```

---

## Multi-Tool Step Sequence

When the agent runs more than one tool in a single turn (e.g., web search →
database query → place pin), the UI must show the **ordered steps** it took, not
just a count. This is the primary enhancement in this revision.

Requirements:
1. **Preserve order** — `metadata.tool_calls` is appended in call order by the
   streaming callback and by `_merge_db_activity`; the frontend must render steps
   in that array order.
2. **Number the steps** — display as an ordered trail (`1`, `2`, `3`, …), each
   labelled with the tool's display name and a status icon.
3. **Live progression** — during streaming, each tool-start event adds the next
   step with an in-progress spinner; the final event flips completed steps to
   success/failure.
4. **Do not collapse repeats** — if the same tool runs multiple times (e.g.,
   three `place_pin` calls), show each as its own numbered step so the user sees
   exactly how many times it ran.
5. **Summarize per step** — where available, show the step's input/output
   summary (e.g., `place_pin → "Eiffel Tower"`, `database_query → 3 rows`).

Example trail (expanded):
```
🔧 3 steps  ▾
1. ✅ Web Search        1.2s   query: 'pod health check' → 3 results
2. ✅ Database Query    0.3s   sample → 3 rows
3. ✅ Place Pin         0.1s   "Eiffel Tower"
```

---

## Backend Requirements

### 1. Tool Event Emission in Streaming

> **Status: partially implemented.** The streaming callback already emits an
> ordered `tool_calls` list per event (`{name, status}`) and a `thinking`
> label on tool start. Remaining: per-tool enrichment (`display_name`,
> `input_summary`, `output_summary`, `duration_ms`) for tools other than
> `database_query`, and explicit start/complete transitions.

Extend the streaming path in [chat_service.py](../backend/services/chat_service.py) (`stream_message`) so every tool emits enriched activity when it is invoked. The list **must remain ordered by call sequence and must not collapse repeated invocations of the same tool** — each call is its own step.

Each tool service (graph artifact, knowledge base, web search, database query, place pin, etc.) should record an activity entry at start and completion. The `database_query` `activity_sink` pattern is the reference implementation to generalize:

```python
# Detailed activity record (as implemented for database_query)
{
    "name": str,        # Internal tool name (e.g., "database_query")
    "status": str,      # "in_progress" | "success" | "error"
    "duration": int,    # Elapsed time in ms
    "inputs": dict,     # Sanitized/truncated input description
    "outputs": dict,    # Counts only — never raw row data
}
```

Target schema to converge on for all tools:

```python
# Tool event schema (target)
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

> **Status: partially implemented.** Streaming currently emits a generic
> `Using <tool>...` label on each tool start. The context-aware mapping below
> is the target refinement.

Replace the generic `Using <tool>...` label with context-aware labels:

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

> **Status: implemented.** The final `done: true` event carries the ordered
> `metadata.tool_calls` list; `database_query` entries include
> `duration`/`inputs`/`outputs`. Enrichment for other tools is pending.

The final `done: true` event includes the full ordered list of tool invocations in `metadata.tool_calls`:

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

> **Status: not started.** The current type is
> `tool_calls?: Array<{ name?: string; input?: Record<string, unknown> }>`.
> Extend it to the richer `ToolCall` shape below (order in the array is
> significant — it is the step sequence).

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

> **Status: partially implemented.** `chatStore` already reads `payload.thinking`
> (→ `uiStore.setThinking`) and applies `metadata.tool_calls` on the `done`
> event. Remaining: apply the **ordered** `tool_calls` list from *interim*
> events too, so steps appear live rather than only at completion.

The stream carries an ordered `tool_calls` list in every event's `metadata`:
- On each event, replace the in-progress message's `metadata.tool_calls` with
  the latest ordered list (it only grows and is already in call order).
- Preserve array order exactly — it **is** the step sequence; never sort or
  de-duplicate repeated tools.
- Update `uiStore.thinkingText` with the `thinking` value when present.

### 3. Tool Activity Component (`components/ToolActivity.vue`)

> **Status: not started.** No `ToolActivity.vue` exists yet; `Message.vue` shows
> only a `Tool calls: N` badge.

A new component rendered inside `Message.vue` for agent messages that have tool calls. It renders the **ordered step trail** described in "Multi-Tool Step Sequence".

**Collapsed state (default):**
```
🔧 3 steps  ▸
```

**Expanded state (numbered, in execution order):**
```
🔧 3 steps  ▾
┌──────────────────────────────────────────┐
│ 1. ✅ Web Search                 1.2s    │
│    query: 'kubernetes pod health check'  │
│    Found 3 relevant results              │
├──────────────────────────────────────────┤
│ 2. ✅ Database Query             0.3s    │
│    sample → 3 rows                       │
├──────────────────────────────────────────┤
│ 3. ❌ Graph Generation           0.8s    │
│    Error: insufficient data points       │
└──────────────────────────────────────────┘
```

**Design details:**
- Steps are **numbered and rendered in execution order**; a tool that runs more
  than once appears as multiple separate steps (never merged).
- Status icons: `✅` success/completed, `❌` error/failed, `⏳` in-progress
  (animated spinner).
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

> **Status: partially implemented.** `Message.vue` currently renders a
> `Tool calls: N` badge; replace it with the `ToolActivity` step trail.

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
1. **Unit test**: The streaming callback records tool invocations in an ordered `tool_calls` list (`{name, status}`) in call order. _(base behavior implemented)_
2. **Unit test**: Multiple tool calls in one turn produce one ordered step per invocation, and repeated calls of the same tool are **not** collapsed.
3. **Unit test**: `_merge_db_activity` merges detailed `database_query` records (`duration`, `inputs`, `outputs`) into the matching `tool_calls` entry in order. _(covered via `database_query` activity_sink tests)_
4. **Unit test**: Thinking text updates to reflect the active tool on a tool-start event.
5. **Integration test**: Streaming endpoint emits the growing `metadata.tool_calls` list between chunk events when tools are invoked.
6. **Edge case**: A tool failure records an `error`/`failed` step with a sanitized summary and the stream continues.

### Frontend
1. **Unit test**: `ToolActivity.vue` renders the correct step count, numbered steps in order, icons, and labels for success/failed steps.
2. **Unit test**: Repeated tools render as separate numbered steps (no de-duplication).
3. **Unit test**: Expand/collapse toggles visibility of the step trail.
4. **Unit test**: `chatStore` applies the ordered `tool_calls` list from interim and final stream events, preserving order.
5. **Integration test**: End-to-end stream with multiple tools renders the live indicator and the final ordered step trail.

---

## Acceptance Criteria

1. When the agent runs multiple tools in one turn, the completed message shows an
   **ordered, numbered step trail** reflecting exactly which tools ran and in what
   sequence.
2. Repeated invocations of the same tool appear as distinct steps (e.g., three
   `place_pin` calls → 3 steps), never merged into one.
3. The step trail is collapsed by default (`🔧 N steps`) and expands to show each
   step's status icon, duration (where available), and input/output summary.
4. During streaming, a live thinking indicator reflects the active tool, and steps
   appear/progress as tools start and complete.
5. `database_query` steps display their row-count summary; other tools display at
   least name + status until per-tool enrichment lands.
6. No raw payloads, credentials, or PII are surfaced; summaries are truncated.
7. Backend and frontend test suites (including the new ordered/multi-tool tests)
   pass.

---

## Phase 2 Considerations

- **Tool call input/output viewer**: Full (redacted) input/output in a modal for debugging.
- **Tool execution timeline**: Gantt-style visualization showing parallel/sequential tool execution.
- **Tool retry from UI**: Allow users to re-run a failed tool call.
- **Tool usage analytics**: Track tool call frequency, duration, and failure rates across conversations.
- **Streaming tool output**: Show partial tool results as they arrive (e.g., search results appearing one by one).
