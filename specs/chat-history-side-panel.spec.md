# Spec: Add Side Chat History Panel with Chat Selection

## Purpose
Provide a persistent side panel that lists past chats and allows users to select and resume prior conversations.

## Problem Statement
Users currently lack an organized way to revisit previous conversations. This makes it difficult to continue work, compare prior outputs, or recover useful context.

## Goals
- Add a left-side (or configurable side) chat history panel.
- Persist and display historical conversations with metadata.
- Enable selecting a previous chat to load its full message thread.
- Support creation of new chats while preserving prior chat sessions.

## Non-Goals
- No cross-device cloud sync in this feature.
- No full-text search across chat history in this initial version.
- No folder/tag organization beyond a flat chronological list.

## User Stories
- As a user, I can see a list of my previous chats in a side panel.
- As a user, I can click a past chat and load its messages into the main chat window.
- As a user, I can start a new chat without losing access to prior chats.
- As a user, I can identify chats by title and last-updated timestamp.

## Functional Requirements
1. UI must include a dedicated chat history panel visible on desktop.
2. Panel must show a list of chats with at least:
   - `title`
   - `updatedAt`
   - optional message preview snippet
3. Selecting a chat in the panel must load that chat's message thread into main chat area.
4. UI must include a "New Chat" action that creates a new empty conversation and sets it active.
5. Active chat item must be visually highlighted in the list.
6. Chat list must be sorted descending by `updatedAt`.
7. When a new message is sent/received, the active chat's `updatedAt` must update and list order must refresh.
8. On app reload, last active chat should be restored when available.

## UX Requirements
- Desktop layout:
  - History panel anchored to side (default left) with resizable/collapsible behavior optional.
- Mobile layout:
  - Panel should open as drawer/sheet with explicit toggle button.
- Empty state:
  - Show helpful text when no chats exist: "No chats yet. Start a new conversation."
- Loading state:
  - Show skeleton/list placeholder while chat list is loading.
- Error state:
  - Show non-blocking inline error if history fetch fails.

## Data Model Requirements
### Chat Summary
```json
{
  "id": "chat_123",
  "title": "Plan Docker setup",
  "updatedAt": "2026-06-24T15:10:00Z",
  "createdAt": "2026-06-24T14:50:00Z",
  "messageCount": 12,
  "preview": "Let's containerize frontend and backend..."
}
```

### Chat Detail
```json
{
  "id": "chat_123",
  "title": "Plan Docker setup",
  "messages": [
    {
      "id": "msg_1",
      "role": "user",
      "content": "...",
      "timestamp": "2026-06-24T14:50:10Z"
    }
  ]
}
```

## Backend Requirements
1. Provide endpoint to list chat summaries:
   - `GET /api/chats`
2. Provide endpoint to fetch one chat detail:
   - `GET /api/chats/:id`
3. Provide endpoint to create new chat session:
   - `POST /api/chats`
4. Existing chat message flow must associate messages with active chat ID.
5. Backend must persist chats/messages (file, DB, or other configured storage) with stable IDs.

### Response Contracts
`GET /api/chats`
```json
{
  "success": true,
  "data": {
    "chats": []
  }
}
```

`GET /api/chats/:id`
```json
{
  "success": true,
  "data": {
    "chat": {}
  }
}
```

`POST /api/chats`
```json
{
  "success": true,
  "data": {
    "chat": {}
  }
}
```

## Frontend Requirements
1. Add chat-session state to store:
   - `chatSummaries`
   - `activeChatId`
   - `activeChatMessages`
2. Add store actions:
   - `loadChats()`
   - `selectChat(chatId)`
   - `createChat()`
   - `syncActiveChatMetadata()`
3. Add side panel component for chat history list and interactions.
4. Keep current message component behavior while loading selected chat messages.
5. Ensure sending a message uses `activeChatId` context.

## Persistence Requirements
- Persist last selected chat ID in localStorage key: `chat.activeId`.
- On startup:
  - load chat summaries
  - restore `chat.activeId` if valid
  - fallback to newest chat or create empty chat if none exists

## Edge Cases
1. Selected chat deleted/missing:
   - clear invalid active ID and select fallback chat.
2. Backend unavailable:
   - display error, preserve in-memory current session if possible.
3. Very long chat titles:
   - truncate with ellipsis and full title on hover/tooltip.
4. Race condition when quickly switching chats:
   - only latest selection response should update UI.

## Security and Validation
- Validate `chatId` format server-side.
- Sanitize rendered title/preview text as plain text.
- Enforce maximum title length and message payload limits.

## Acceptance Criteria
1. Side panel displays list of prior chats with title and timestamp.
2. Clicking a chat loads its full messages in main chat view.
3. New Chat creates and activates a fresh conversation.
4. Active chat persists across page refresh.
5. Sending/receiving messages updates chat ordering by recent activity.
6. Existing chat behavior remains functional with no regressions.

## Test Cases
- Unit:
  - Chat list sorting by updated time.
  - Active chat persistence and fallback behavior.
- Component:
  - Active chat visual highlight updates on selection.
  - Empty/loading/error panel states render correctly.
- Integration:
  - Create chat -> send message -> reload -> same chat restores.
  - Switch between two chats and verify isolated message threads.
- API:
  - `GET /api/chats` returns stable summary shape.
  - `GET /api/chats/:id` handles unknown ID with structured error.

## Implementation Notes
- Start with simple storage abstraction to allow future DB migration.
- Keep panel modular so search/filter can be added later without redesign.
- Optionally auto-generate title from first user message when title is empty.
