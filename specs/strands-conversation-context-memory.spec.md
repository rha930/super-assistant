# Spec: Add Conversation History Context in Strands Agent

## Purpose
Enable the Strands agent to refer back to prior messages in the same conversation by persisting chat history and injecting relevant history into each new agent turn.

## Problem Statement
The current chat flow does not reliably provide prior conversation turns to Strands on each request. This causes context loss, repeated questions, and weaker multi-turn reasoning.

## Goals
- Persist conversation history per conversation ID.
- Supply conversation history to Strands for each new user message.
- Keep context window bounded with truncation/summarization strategy.
- Preserve existing chat API behavior while improving answer continuity.

## Non-Goals
- No cross-user/shared conversation memory in this feature.
- No long-term vector memory retrieval across unrelated conversations.
- No model fine-tuning workflow.

## User Stories
- As a user, when I ask follow-up questions, the agent remembers what was said earlier.
- As a user, the agent can reference earlier decisions and constraints from the same thread.
- As a user, I can continue a conversation after refresh by using the same conversation ID.

## Functional Requirements
1. Backend must persist messages for each conversation using a stable conversation ID.
2. Incoming chat requests must accept and use conversation ID to load prior history.
3. Before invoking Strands, backend must construct context from conversation history plus current user prompt.
4. Context must preserve role order (system, user, assistant/agent) and chronology.
5. New agent responses must be appended to stored conversation history.
6. If conversation ID is absent, backend creates a new one and returns it to frontend.
7. If conversation ID is provided but unknown, backend may initialize a new conversation with that ID (or return structured error based on policy).

## Strands Integration Requirements
1. Strands invocation layer must accept a list of prior messages as conversation context.
2. Message mapping must convert app roles to Strands-compatible role format.
3. Context payload should include:
   - system prompt (resolved config)
   - selected recent messages (windowed)
   - optional condensed summary (if enabled)
   - current user message
4. Existing tool-call handling in Strands should continue to work with history-enabled prompts.

## Context Construction Rules
- Message ordering: oldest to newest.
- Recency policy:
  - Include last N turns by default (configurable, recommended N=12 messages).
- Token budget policy:
  - Reserve output tokens first.
  - Use remaining budget for context.
  - Trim oldest messages first if budget exceeded.
- Optional summary fallback:
  - When history exceeds threshold, include a short generated summary + latest turns.

## Data Model Requirements
### Conversation
```json
{
  "id": "conv_abc123",
  "created_at": "2026-06-24T12:00:00Z",
  "updated_at": "2026-06-24T12:15:00Z",
  "summary": "Optional running summary",
  "metadata": {
    "model": "llama3.1:8b"
  }
}
```

### Message
```json
{
  "id": "msg_001",
  "conversation_id": "conv_abc123",
  "role": "user",
  "content": "What are the deployment steps?",
  "timestamp": "2026-06-24T12:10:00Z",
  "metadata": {}
}
```

## Backend Requirements
1. Storage layer:
   - Add repository/service methods for create/get conversation, append/get messages.
2. Chat route behavior:
   - Load conversation history before Strands call.
   - Build context and pass to Strands service.
   - Persist user and agent messages after each turn.
3. History endpoints (if not already present) should return full or paginated history by conversation ID.
4. Add safeguards against unbounded growth (retention policy or summarization checkpoints).

## API Contract Requirements
### POST /api/chat/message or /api/chat/stream
Request:
```json
{
  "message": "follow-up question",
  "conversation_id": "conv_abc123"
}
```

Response (success):
```json
{
  "success": true,
  "data": {
    "message": "agent response",
    "conversation_id": "conv_abc123"
  }
}
```

Streaming events should continue to include conversation_id in payload.

## Frontend Requirements
1. Frontend must continue sending conversation_id for subsequent turns.
2. On first response with generated conversation_id, frontend stores and reuses it.
3. Chat history load behavior should align with backend persisted messages.
4. No breaking changes to existing message rendering.

## Configuration Requirements
Add configurable limits in backend config:
- CONTEXT_MAX_MESSAGES (default 12)
- CONTEXT_MAX_INPUT_TOKENS (model-aware budget)
- CONTEXT_SUMMARY_ENABLED (true/false)
- CONTEXT_SUMMARY_TRIGGER_MESSAGES (default 40)

## Edge Cases
1. Missing/invalid conversation ID:
   - Create new conversation and continue.
2. Corrupt/empty history:
   - Continue with current user message only and log warning.
3. Oversized single user message:
   - Truncate or reject with structured validation error.
4. Concurrent writes to same conversation:
   - Ensure ordering and consistency via timestamp/transaction strategy.

## Security and Privacy
- Treat conversation history as sensitive data.
- Do not log full message content at error level in production.
- Support future data deletion by conversation ID.
- Ensure tenant/user isolation when auth is present.

## Telemetry (Optional)
- Event: context_history_loaded
  - Properties: conversation_id, message_count, truncated_count
- Event: context_summary_used
  - Properties: conversation_id, summary_length

## Acceptance Criteria
1. Follow-up questions correctly reference earlier turns in the same conversation.
2. Conversation continuity is preserved after page refresh when conversation_id is reused.
3. Context builder enforces max message/token limits without crashes.
4. Backend persists both user and agent turns for each request.
5. Existing chat endpoints and streaming remain functional.

## Test Cases
- Unit:
  - Context builder selects and orders messages correctly.
  - Token/message budget trimming removes oldest messages first.
  - Role mapping to Strands format is correct.
- Integration:
  - Multi-turn conversation: second/third turns use earlier context.
  - Refresh and continue with same conversation_id preserves continuity.
  - Unknown conversation_id behavior matches policy.
- Regression:
  - Streaming chat still emits chunks and conversation_id.
  - Tool-calling flows still function with history-enabled context.

## Rollout Plan
1. Add storage methods and context builder in backend services.
2. Integrate context builder into Strands agent call path.
3. Add tests for context selection/trimming and multi-turn behavior.
4. Validate with long conversations and streaming.
5. Optionally enable summary mode behind config flag.

## Implementation Notes
- Prefer single context builder utility to avoid duplicated logic across routes/services.
- Keep summaries optional and incremental to minimize latency.
- Start with recency window + token cap, then add summary enhancement as phase 2.
