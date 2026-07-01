# Spec: User Chat History Storage and Retrieval (Phased)

## Purpose
Add persistent user-scoped chat history so the agent can store and retrieve prior messages reliably across requests and sessions.

## Problem Statement
Current conversation history is held in process memory (`self.conversations`) and is not durable. This causes history loss on restart, no user-level isolation beyond conversation IDs, and limited scalability.

## Goals
- Persist chat history per user and per conversation.
- Support retrieval for agent context and history endpoints.
- Keep first implementation simple/local with bounded storage.
- Introduce a second implementation using Redis for production-grade persistence and scale.

## Non-Goals
- No long-term analytics/BI pipeline in this feature.
- No vector embeddings/RAG memory in this feature.
- No cross-region replication strategy in this feature.

## User Stories
- As a user, I can return later and continue a previous conversation.
- As a user, my history is isolated from other users.
- As an operator, I can run locally without external infra in phase 1.
- As an operator, I can switch to Redis in phase 2 for better durability and performance.

## Functional Requirements
1. Every stored message must include `user_id`, `conversation_id`, `role`, `content`, `timestamp`, and optional `metadata`.
2. Backend must append user and agent messages to persistent storage for both sync and streaming paths.
3. Backend must retrieve conversation history from storage (not in-memory) for context-building.
4. History retrieval endpoint must support user scoping and pagination/limits.
5. Storage implementation must enforce configurable retention/limits.
6. Backend must provide abstraction layer so phase 1 and phase 2 share the same service interface.

## Architecture Overview
Introduce a storage abstraction:
- `ChatHistoryRepository` (interface/protocol)
- `LocalChatHistoryRepository` (phase 1)
- `RedisChatHistoryRepository` (phase 2)

`ChatService` uses only the repository interface.

## Data Contract

### Message Record
```json
{
  "id": "msg_...",
  "user_id": "user_123",
  "conversation_id": "conv_abc",
  "role": "user|agent|assistant|system",
  "content": "text",
  "timestamp": "2026-06-24T12:34:56.789Z",
  "metadata": {
    "artifacts": [],
    "tool_calls": []
  }
}
```

### Conversation Record (optional aggregate)
```json
{
  "conversation_id": "conv_abc",
  "user_id": "user_123",
  "created_at": "...",
  "updated_at": "...",
  "message_count": 42
}
```

## API Changes

### Existing Endpoints (modified behavior)
1. `POST /api/chat/message`
- Must accept `user_id` (header or body; define one canonical source).
- Must persist both user input and agent output to repository.

2. `POST /api/chat/stream`
- Same user scoping behavior.
- Must persist final agent message via repository in `finalize_stream_message`.

3. `GET /api/chat/history/<conversation_id>`
- Must require and validate `user_id` ownership.
- Must return paginated/limited history.

### Optional New Endpoints
1. `GET /api/chat/conversations`
- List a user’s conversations (recent first).

2. `DELETE /api/chat/history/<conversation_id>`
- Delete one user-owned conversation.

## Phase 1: Local Persistent Storage (Limited)

### Storage Option
Use local SQLite file (recommended) or file-backed JSON store.

Recommendation:
- SQLite at `backend/data/chat_history.db`
- WAL mode enabled for safe concurrent reads/writes in local dev.

### Schema (SQLite)
```sql
CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_conversation_time
ON chat_messages(user_id, conversation_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_chat_messages_user_time
ON chat_messages(user_id, timestamp);
```

### Retention / Limits
Config keys:
- `history_config.max_messages_per_conversation` (default: 200)
- `history_config.max_conversations_per_user` (default: 50)
- `history_config.max_message_chars` (default: 20000)

Behavior:
- Trim oldest messages beyond per-conversation cap.
- Optionally trim oldest conversations beyond cap.

### Local Dev Requirements
- No external dependency required.
- DB auto-created on startup if missing.
- Safe fallback to in-memory only if DB unavailable (with warning log).

## Phase 2: Redis-Backed Storage

### Redis Data Model (recommended)
1. Sorted set for conversation messages by timestamp:
- Key: `chat:{user_id}:{conversation_id}:messages`
- Member: serialized message JSON
- Score: epoch millis

2. Sorted set for conversation recency:
- Key: `chat:{user_id}:conversations`
- Member: `conversation_id`
- Score: last_updated epoch millis

3. Optional hash for conversation metadata:
- Key: `chat:{user_id}:{conversation_id}:meta`

### Retention / Limits
- Use `ZREMRANGEBYRANK` for message trimming per conversation.
- Use `ZREMRANGEBYRANK` to trim old conversations per user.
- Optional key TTL for inactive conversations.

### Redis Config
Add `history_backend` config:
- `history_backend.type`: `local` | `redis`
- `history_backend.redis_url`
- `history_backend.redis_prefix` (default: `chat`)

## Backend Refactor Requirements
1. Create repository interface in `backend/services/history_repository.py`.
2. Implement local repository in `backend/services/history_repository_local.py`.
3. Implement redis repository in `backend/services/history_repository_redis.py`.
4. Wire repository selection in app startup/config service.
5. Replace direct use of `self.conversations` in `ChatService` with repository calls.
6. Preserve existing response contracts so frontend remains compatible.

## Security & Privacy
- Validate `user_id` format and length.
- Authorize conversation ownership on read/delete endpoints.
- Avoid logging full message content in info/error logs.
- Ensure metadata serialization handles untrusted input safely.

## Migration Strategy
1. Phase 1 deploy with local DB and repository abstraction.
2. Keep current in-memory structure as temporary fallback only.
3. Add feature flag/config switch for `history_backend.type`.
4. Phase 2 deploy Redis implementation behind same interface.
5. Optional migration script to copy local SQLite records to Redis.

## Observability
- Metrics:
  - `history_write_success_total`
  - `history_write_failure_total`
  - `history_read_latency_ms`
  - `history_trimmed_messages_total`
- Logs:
  - backend type on startup
  - repository fallback events
  - ownership check failures

## Acceptance Criteria
1. Restarting backend in phase 1 does not lose user conversation history.
2. `GET /api/chat/history/<conversation_id>` returns only data owned by requesting user.
3. Context-building in chat uses persisted history from repository.
4. Retention limits are enforced automatically.
5. Switching `history_backend.type` from `local` to `redis` requires no `ChatService` code change.
6. Streaming and non-streaming paths both persist final agent responses.

## Test Plan

### Unit Tests
- Repository interface contract tests (shared test suite for local + redis).
- Retention trimming logic tests.
- Ownership validation tests.

### Integration Tests
- Sync chat write/read roundtrip with user scoping.
- Stream chat finalize write/read roundtrip.
- Restart backend (phase 1) and verify history persists.

### Redis-Specific Tests (Phase 2)
- Key naming and isolation by user/conversation.
- Trimming via sorted set rank limits.
- Redis unavailable behavior and fallback strategy.

## Rollout Plan
1. Implement repository abstraction + local backend.
2. Enable local backend as default.
3. Add Redis backend and configuration toggle.
4. Validate in staging with synthetic multi-user load.
5. Promote Redis backend for production environments.

## Open Questions
1. Canonical `user_id` source: auth token claim vs header vs request body?
2. Should anonymous users be allowed? If yes, how is identity persisted (cookie/session ID)?
3. Is hard delete required for compliance, or soft-delete acceptable?
4. What retention default is acceptable for production cost constraints?

## Implementation Notes
- Keep current `conversation_id` generation for compatibility, but ensure repository-level uniqueness constraints.
- Prefer UTC ISO 8601 timestamps throughout.
- Keep phase 1 simple and robust; avoid overfitting with premature distributed concerns.
