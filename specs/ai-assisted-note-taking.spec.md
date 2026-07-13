# Spec: AI-Assisted Note-Taking with LLM Expansion

## Purpose
Add a note-taking panel to the application where users can write, format, and save notes — with an AI-powered "note-taking mode" that detects note intent, transcribes conversation topics into the active note, and offers to expand/format content using the LLM before committing it.

## Problem Statement
Users currently have no way to capture and organize information during or outside of chat sessions. When the agent surfaces useful data — a plan, a list, a summary — the user must manually copy it elsewhere. There is also no structured way to quickly jot down ideas and have the AI flesh them out into well-formatted, useful notes (e.g., typing "grocery list" and getting a pre-populated, formatted list).

## Goals
- Add a **Notes panel** (new tab/aside) for creating, editing, formatting, and saving notes.
- Implement a **note-taking mode** where each chat message is treated as note content rather than a general conversation.
- In note-taking mode, the LLM **expands and auto-formats** the user's input before adding it to the note (e.g., "grocery list" → a Markdown list pre-filled with common items).
- Present the LLM suggestion and let the user **accept (a)**, **deny (d)**, or **expand more (e)** before committing to the note.
- Each subsequent message in note-taking mode **appends to the same active note**.
- Users can **save notes, browse past notes, and reopen them**.

## Non-Goals
- No real-time collaboration or multi-user note editing.
- No rich text editor (WYSIWYG) — notes use Markdown rendered to formatted display.
- No file attachment or image embedding in notes.
- No note sharing or export in Phase 1.
- No voice-to-text transcription — "transcribe" refers to the LLM expanding typed input.
- No integration with external note services (Notion, Evernote, etc.).

---

## User Stories

1. As a user, I can open a **Notes tab** from the header and see my note workspace.
2. As a user, I can **create a new note**, give it a title, and type content with Markdown formatting that renders automatically.
3. As a user, I can **save a note** and later **browse and reopen past notes** from a list.
4. As a user, I can **enter note-taking mode** so that my chat messages feed into the active note instead of a general conversation.
5. As a user, when I type a short phrase in note-taking mode (e.g., "grocery list"), the LLM **expands it** into a well-formatted note with sensible defaults and presents it for my review.
6. As a user, I can **accept (a)** the LLM's suggestion to add it to my note, **deny (d)** to keep only my original text, or **expand more (e)** to have the LLM add even more detail.
7. As a user, each subsequent message in note-taking mode **appends to the same note** I'm working on.
8. As a user, I can **exit note-taking mode** and return to normal chat.
9. As a user, I can **delete notes** I no longer need.

---

## Architecture

### High-Level Flow
```
┌──────────────────────────────────────────────────────────┐
│  App.vue                                                 │
│  ┌──────────────┐  ┌────────────────────────────────┐    │
│  │  ChatWindow   │  │  NotesPanel (new aside)        │    │
│  │               │  │  ┌──────────────────────────┐  │    │
│  │  [normal or   │  │  │ Note List / Note Editor   │  │    │
│  │   note-taking │  │  │ (Markdown + rendered view)│  │    │
│  │   mode]       │  │  │                            │  │    │
│  │               │  │  └──────────────────────────┘  │    │
│  └──────────────┘  └────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘

Note-Taking Mode Flow:
User types "grocery list"
    │
    ▼
┌──────────────────┐
│  ChatService     │  detects note-taking mode
│  (note prompt)   │  uses note-expansion system prompt
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  LLM Provider    │  generates expanded, formatted note content
│  (Ollama/Gemini) │
└────────┬─────────┘git c
         │
         ▼
┌──────────────────────────────────────────────┐
│  Agent response with suggestion              │
│  "Here's an expanded grocery list: ..."       │
│  [Accept (a)] [Deny (d)] [Expand more (e)]   │
└──────────────────────────────────────────────┘
         │
    User picks action
         │
    ┌────┼────┐
    a    d    e
    │    │    │
    ▼    ▼    ▼
  Add   Add  Re-prompt LLM
  LLM   raw  with "expand more"
  text  text  → new suggestion
  to    to
  note  note
```

### Component Map
| Component | File | Role |
|---|---|---|
| NotesPanel | `frontend/src/components/NotesPanel.vue` (new) | Note editor/viewer panel |
| NoteEditor | `frontend/src/components/NoteEditor.vue` (new) | Markdown editor + preview |
| notesStore | `frontend/src/stores/notesStore.ts` (new) | Notes state, note-taking mode, CRUD |
| Note types | `frontend/src/types/note.ts` (new) | TypeScript interfaces |
| NoteService | `backend/services/note_service.py` (new) | Note CRUD + LLM expansion |
| NoteRepository | `backend/services/note_repository.py` (new) | SQLite persistence for notes |
| Notes routes | `backend/routes/notes.py` (new) | REST API for notes |
| ChatService | `backend/services/chat_service.py` (modified) | Note-taking mode routing |
| Config | `backend/config.py` (modified) | Note-expansion system prompt |

---

## Functional Requirements

### Notes Panel (FR-1)
1. A new **Notes** icon button in the App header toggles a `NotesPanel` aside (same pattern as HistoryPanel/ConfigPanel, `w-96`).
2. The panel has two views:
   - **Note List**: shows saved notes with title, last-modified date, and a preview snippet. Supports create-new and delete.
   - **Note Editor**: shows the active note with a title field and a Markdown body editor. Content auto-renders formatted Markdown below or beside the editor.
3. Clicking a note in the list opens it in the editor. Clicking "New Note" creates a blank note.

### Note-Taking Mode (FR-2)
1. A **"Note-Taking Mode"** toggle (button or switch) is visible when the Notes panel is open or from the chat input area.
2. When note-taking mode is active:
   - The chat input area shows a visual indicator (e.g., colored border, label: "Note-taking mode — messages will be added to: [note title]").
   - An active note must be selected (or a new one is auto-created with a timestamped title).
   - The Notes panel auto-opens if not already open.
3. Exiting note-taking mode returns to normal chat. The toggle, a chat command `/note off`, or closing the Notes panel all exit the mode.

### LLM Expansion (FR-3)
1. When the user sends a message in note-taking mode, the message is sent to the LLM with a **note-expansion system prompt** that instructs the model to:
   - Expand the user's short input into well-formatted Markdown.
   - Pre-fill sensible defaults (e.g., "grocery list" → a list with common items).
   - Maintain context of the existing note content when appending.
2. The LLM response is displayed in the chat as a **suggestion**, not immediately committed to the note.

### Accept / Deny / Expand (FR-4)
1. After the LLM presents a suggestion, the chat shows three action buttons: **Accept**, **Deny**, **Expand More**.
2. The user can also type **"a"**, **"d"**, or **"e"** as shorthand (case-insensitive).
3. **Accept (a)**:
   - The LLM's expanded/formatted content is appended to the active note.
   - The note auto-saves.
   - The chat confirms: "Added to note: [title]".
4. **Deny (d)**:
   - The user's original raw input (before LLM expansion) is appended to the note as-is.
   - The note auto-saves.
   - The chat confirms: "Original text added to note: [title]".
5. **Expand More (e)**:
   - The LLM is re-prompted with the previous suggestion and asked to add more detail/content.
   - A new suggestion is presented with the same accept/deny/expand options.
   - This can repeat multiple times.
6. While a suggestion is pending, normal messages are blocked — the user must resolve the suggestion first (or cancel with "d").

### Appending to Notes (FR-5)
1. Each subsequent message in note-taking mode **appends** to the active note's body (separated by a blank line or section divider).
2. The LLM receives the existing note content as context so expansions are coherent with prior content.
3. The note editor updates in real-time as content is accepted.

### Note Persistence (FR-6)
1. Notes are saved to the backend via REST API.
2. Auto-save triggers on accept/deny actions and periodically (every 30 seconds if dirty).
3. Notes persist across sessions — reloading the app shows saved notes.
4. Users can manually save with a save button or Cmd/Ctrl+S in the editor.
5. Users can delete notes from the note list (with confirmation).

---

## Backend Requirements

### Data Model — `notes` Table

New SQLite table in the existing DB (`chat_history.db`):

```sql
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'Untitled Note',
    content TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_user_updated
    ON notes (user_id, updated_at DESC);
```

### New Service: `services/note_repository.py`

Follows the `LocalChatHistoryRepository` pattern — SQLite-backed CRUD:

```python
class NoteRepository:
    def __init__(self, db_path: str = './backend/data/chat_history.db'):
        ...

    def create_note(self, user_id: str, title: str = 'Untitled Note', content: str = '') -> dict:
        """Create a new note. Returns { id, user_id, title, content, created_at, updated_at }."""

    def get_note(self, user_id: str, note_id: str) -> dict | None:
        """Get a single note by ID. Returns None if not found or wrong user."""

    def update_note(self, user_id: str, note_id: str, title: str | None = None, content: str | None = None) -> dict:
        """Update note title and/or content. Returns updated note."""

    def append_content(self, user_id: str, note_id: str, content: str) -> dict:
        """Append content to an existing note body (separated by \\n\\n). Returns updated note."""

    def delete_note(self, user_id: str, note_id: str) -> bool:
        """Delete a note. Returns True if deleted."""

    def list_notes(self, user_id: str, limit: int = 50) -> list[dict]:
        """List user's notes ordered by updated_at DESC. Returns list of { id, title, updated_at, preview }."""
```

### New Service: `services/note_service.py`

Orchestrates LLM expansion and note management:

```python
class NoteService:
    def __init__(self):
        self.note_repo = NoteRepository()
        self.config_service = get_config_service()

    def expand_note_content(
        self,
        user_input: str,
        existing_note_content: str,
        user_id: str,
        conversation_id: str | None = None,
    ) -> dict:
        """Send user input to the LLM with the note-expansion prompt.

        Returns: {
            'suggestion': str,          # LLM-expanded content (Markdown)
            'original_input': str,      # The raw user input
            'note_id': str,
            'conversation_id': str,
        }
        """

    def accept_suggestion(self, user_id: str, note_id: str, suggestion: str) -> dict:
        """Append the LLM suggestion to the note. Returns updated note."""

    def deny_suggestion(self, user_id: str, note_id: str, original_input: str) -> dict:
        """Append the user's raw input to the note. Returns updated note."""

    def expand_more(
        self,
        previous_suggestion: str,
        existing_note_content: str,
        user_id: str,
    ) -> dict:
        """Re-prompt the LLM to add more detail to the previous suggestion.

        Returns: { 'suggestion': str }
        """
```

**Note-expansion system prompt** (added to `config.py`):

```python
NOTE_EXPANSION_SYSTEM_PROMPT = """You are a note-taking assistant. The user is building a note and will give you short inputs.
Your job is to expand their input into well-formatted Markdown content suitable for a note.

Rules:
- Expand short phrases into structured, useful content (lists, headings, paragraphs).
- Pre-fill sensible defaults when the topic is common (e.g., "grocery list" → a list with common items).
- Use proper Markdown formatting: headings (#), lists (-), bold (**), etc.
- If existing note content is provided, make your addition coherent with it.
- Keep expansions concise but useful — aim for practical, actionable content.
- Do NOT wrap your response in a code fence. Return raw Markdown only.
- Do NOT include preamble like "Here's your expanded note:". Just return the content."""
```

### New Routes: `routes/notes.py`

Blueprint at `/api/notes`, all `@require_auth`:

| Method | Path | Description | Request | Response `data` |
|---|---|---|---|---|
| `POST` | `/api/notes` | Create a note | `{ title?, content? }` | `{ note }` |
| `GET` | `/api/notes` | List user's notes | query: `limit` | `{ notes: [...] }` |
| `GET` | `/api/notes/<id>` | Get a single note | — | `{ note }` |
| `PUT` | `/api/notes/<id>` | Update title/content | `{ title?, content? }` | `{ note }` |
| `PATCH` | `/api/notes/<id>/append` | Append content | `{ content }` | `{ note }` |
| `DELETE` | `/api/notes/<id>` | Delete a note | — | `{}` |
| `POST` | `/api/notes/expand` | LLM-expand input | `{ input, note_id, existing_content? }` | `{ suggestion, original_input }` |
| `POST` | `/api/notes/expand-more` | Expand a suggestion further | `{ previous_suggestion, existing_content? }` | `{ suggestion }` |

All responses use the standard `{ success, message, data }` shape.

### Chat Service Integration

Modify `stream_message` / `process_message` in `chat_service.py`:

1. Accept an optional `mode` parameter (default `"chat"`, alternative `"note"`).
2. When `mode == "note"`:
   - Use the `NOTE_EXPANSION_SYSTEM_PROMPT` instead of the user's configured system prompt.
   - Include existing note content in the context so the LLM can maintain coherence.
   - Tag response metadata with `{ mode: "note", note_id: "..." }`.

Alternatively, the note expansion can be handled entirely through the dedicated `/api/notes/expand` endpoint (keeping chat and notes decoupled). **Recommended: use dedicated endpoints** to keep concerns separated.

### Docker Compose

No changes needed — the `notes` table lives in the same SQLite DB on the existing `backend-data` volume.

---

## Frontend Requirements

### Types (`types/note.ts`)

```typescript
export interface Note {
  id: string
  user_id: string
  title: string
  content: string
  created_at: string
  updated_at: string
}

export interface NoteSuggestion {
  suggestion: string
  original_input: string
  note_id: string
}
```

### Store (`stores/notesStore.ts`)

```typescript
export const useNotesStore = defineStore('notes', () => {
  // State
  const notes = ref<Note[]>([])
  const activeNote = ref<Note | null>(null)
  const noteTakingMode = ref(false)
  const pendingSuggestion = ref<NoteSuggestion | null>(null)
  const isExpanding = ref(false)
  const isDirty = ref(false)

  // Actions
  async function loadNotes(): Promise<void>
  async function createNote(title?: string): Promise<Note>
  async function openNote(noteId: string): Promise<void>
  async function saveNote(): Promise<void>
  async function deleteNote(noteId: string): Promise<void>
  async function updateTitle(title: string): Promise<void>
  async function updateContent(content: string): void  // local only, marks dirty

  // Note-taking mode
  function enterNoteTakingMode(noteId?: string): void
  function exitNoteTakingMode(): void
  async function expandInput(input: string): Promise<void>
  async function acceptSuggestion(): Promise<void>
  async function denySuggestion(): Promise<void>
  async function expandMore(): Promise<void>

  return { ... }
})
```

### Components

#### `NotesPanel.vue`
- Rendered as an `<aside>` in `App.vue` (same as HistoryPanel), toggled by `showNotesPanel` ref.
- **Two-view layout**:
  - **List view**: Shown when no note is active. Lists notes (title, date, preview snippet). "New Note" button at top. Click to open. Swipe/button to delete (with confirm).
  - **Editor view**: Shown when `activeNote` is set. Back button to return to list. Title input, Markdown textarea, rendered preview below. Save button + note-taking mode toggle.
- Note-taking mode toggle: switch/button that calls `notesStore.enterNoteTakingMode()`.

#### `NoteEditor.vue`
- Extracted sub-component for the editor view.
- Props: `note: Note`, `readonly: boolean`.
- Two-pane or toggle: raw Markdown editor (textarea) + rendered Markdown preview.
- Emits: `update:title`, `update:content`, `save`.

#### Chat Integration (`ChatWindow.vue` / `chatStore.ts`)
- When `noteTakingMode` is active:
  - Chat input shows a visual indicator (e.g., icon, colored left border, label).
  - On send, the message is routed to `notesStore.expandInput()` instead of `chatStore.sendMessage()`.
  - The LLM suggestion appears as a special agent message in the chat with **action buttons**: Accept (a), Deny (d), Expand More (e).
- **Suggestion message component**: A distinct message type (or metadata flag `mode: 'note-suggestion'`) that renders:
  - The formatted suggestion preview (rendered Markdown).
  - Three buttons: `[Accept (a)]` `[Deny (d)]` `[Expand more (e)]`.
- **Shortcut input handling**: When a suggestion is pending and the user types exactly "a", "d", or "e" (case-insensitive, trimmed), intercept it as the corresponding action instead of sending a new message.
- After accept/deny, a confirmation message appears in chat ("Added to note: [title]").
- After expand-more, the new suggestion replaces the old one with the same action buttons.

### Markdown Rendering
- Use an existing lightweight Markdown renderer (e.g., `marked` or `markdown-it`) to render note content in the editor preview and suggestion previews.
- Sanitize rendered HTML to prevent XSS (use `DOMPurify` or equivalent).

---

## UX Requirements

1. **Notes icon**: A document/note icon in the header bar (between the graph icon and history icon, or at the end).
2. **Note-taking mode indicator**: When active, the chat input area has a distinct visual state — colored left border or top banner: `📝 Note-taking mode — [Note title] · [Exit]`.
3. **Suggestion card**: The LLM suggestion in chat is visually distinct from normal messages — a card with a light background, rendered Markdown, and the three action buttons at the bottom.
4. **Action buttons**: Styled consistently with the app theme. Each shows the keyboard shortcut: `Accept (a)`, `Deny (d)`, `Expand more (e)`.
5. **Auto-scroll**: The Notes panel editor scrolls to the bottom when new content is appended.
6. **Empty state**: Note list shows "No notes yet. Create your first note!" when empty.
7. **Confirmation on delete**: "Delete this note? This cannot be undone." dialog.
8. **Dirty indicator**: Show an unsaved-changes dot/indicator on the note title when `isDirty` is true.

---

## Security / Validation Considerations

- All note endpoints require authentication (`@require_auth`).
- Notes are scoped to `user_id` — users can only access their own notes.
- Note `title` is trimmed and capped at 200 characters.
- Note `content` is capped at 100,000 characters (server-side validation).
- User input sent to the LLM for expansion is treated the same as chat messages — standard prompt injection mitigations apply (the note-expansion system prompt is fixed, not user-configurable).
- Rendered Markdown in the frontend is sanitized (DOMPurify) before DOM insertion.
- Note IDs are validated as the expected format before DB queries.

---

## Edge Cases

1. **No active note when entering note-taking mode** → Auto-create a new note with title "Note — [timestamp]".
2. **Note deleted while in note-taking mode** → Exit note-taking mode, show toast: "Note was deleted".
3. **LLM expansion fails** → Show error in chat: "Could not expand note. Your original text has been added." Fall back to deny behavior (append raw input).
4. **Empty input in note-taking mode** → Ignore, don't send to LLM.
5. **Very long note content** → Truncate context sent to LLM to stay within token limits (use last N characters of existing note content, configurable).
6. **User closes Notes panel while suggestion is pending** → Suggestion remains in chat; re-opening the panel restores context. Alternatively, auto-deny on panel close.
7. **Multiple expand-more cycles** → Allow up to 5 sequential expansions, then show "Maximum expansions reached. Accept or deny to continue."
8. **Concurrent editing** → Single-user app, no conflict handling needed. Auto-save uses last-write-wins.
9. **User types "a", "d", or "e" as actual note content** → Only intercept these when `pendingSuggestion` is non-null and the input is exactly one of the shortcut characters (trimmed, case-insensitive). Longer messages containing "a" are treated normally.

---

## Testing Requirements

### Backend Unit Tests

1. **`NoteRepository`**:
   - `create_note` returns a note with generated ID and timestamps.
   - `get_note` returns note for correct user, `None` for wrong user.
   - `update_note` updates title and/or content, bumps `updated_at`.
   - `append_content` appends with `\n\n` separator.
   - `delete_note` removes note, returns `True`; wrong user returns `False`.
   - `list_notes` returns notes ordered by `updated_at` DESC with preview.

2. **`NoteService`**:
   - `expand_note_content` calls LLM with note-expansion system prompt (mock LLM).
   - `accept_suggestion` appends suggestion to note via repository.
   - `deny_suggestion` appends original input to note via repository.
   - `expand_more` re-prompts LLM with previous suggestion as context.

3. **Notes routes**:
   - All CRUD endpoints return correct response shapes.
   - Auth required — 401 without token.
   - User isolation — user A cannot access user B's notes.
   - Validation — title too long, content too long, missing fields.

### Frontend Unit Tests

1. **`notesStore`**:
   - `enterNoteTakingMode` sets flag and auto-creates note if none active.
   - `exitNoteTakingMode` clears flag and pending suggestion.
   - `acceptSuggestion` calls API, clears pending, updates note content.
   - `denySuggestion` calls API with original input, clears pending.
   - `expandMore` calls API, replaces pending suggestion.
   - Shortcut detection: "a"/"d"/"e" (case-insensitive) map to correct actions when suggestion is pending.

2. **`NotesPanel`**:
   - Renders note list when no active note.
   - Renders editor when active note is set.
   - Note-taking mode toggle updates store state.

---

## Acceptance Criteria

1. A Notes icon in the header opens a Notes panel with a list of saved notes.
2. Users can create, edit (title + Markdown body), save, reopen, and delete notes.
3. Note-taking mode can be toggled on/off; chat input shows a clear visual indicator when active.
4. In note-taking mode, typing a short phrase (e.g., "grocery list") produces an LLM-expanded, Markdown-formatted suggestion in the chat.
5. Accept (a) appends the LLM suggestion to the active note; Deny (d) appends the raw input; Expand more (e) produces a more detailed suggestion.
6. Shortcut keys "a", "d", "e" work as alternatives to clicking the buttons.
7. Each subsequent message in note-taking mode appends to the same active note.
8. Notes persist across sessions (backend storage).
9. All backend tests pass; all frontend tests pass.

---

## Implementation Plan

### Phase 1: Notes CRUD (Backend + Frontend)
**Goal**: Basic note creation, editing, saving, and listing — no AI features yet.

1. Create `backend/services/note_repository.py` — SQLite CRUD for notes table.
2. Create `backend/routes/notes.py` — REST endpoints for notes.
3. Register blueprint in `backend/app.py`.
4. Create `frontend/src/types/note.ts` — TypeScript interfaces.
5. Create `frontend/src/stores/notesStore.ts` — Pinia store with CRUD actions.
6. Create `frontend/src/components/NotesPanel.vue` — Panel with list + editor views.
7. Create `frontend/src/components/NoteEditor.vue` — Markdown editor + preview.
8. Add Notes panel toggle to `App.vue` header and aside.
9. Add Markdown rendering dependency (e.g., `marked` + `DOMPurify`).
10. Write backend unit tests for repository and routes.
11. Write frontend unit tests for store and components.

### Phase 2: Note-Taking Mode + LLM Expansion
**Goal**: AI-powered note expansion with accept/deny/expand flow.

1. Add `NOTE_EXPANSION_SYSTEM_PROMPT` to `backend/config.py`.
2. Create `backend/services/note_service.py` — LLM expansion orchestration.
3. Add `/api/notes/expand` and `/api/notes/expand-more` endpoints.
4. Add note-taking mode state to `notesStore.ts` (toggle, pending suggestion).
5. Add note-taking mode indicator to `ChatWindow.vue` input area.
6. Build suggestion message component with Accept/Deny/Expand buttons.
7. Implement shortcut key interception ("a"/"d"/"e") in chat input.
8. Connect accept/deny/expand actions to API and note updates.
9. Add auto-save on accept/deny.
10. Write backend tests for note service (mock LLM).
11. Write frontend tests for note-taking mode flow.

### Phase 3: Polish + Edge Cases
**Goal**: Robustness, UX polish, and edge case handling.

1. Auto-create note when entering note-taking mode with no active note.
2. Handle LLM failure gracefully (fall back to deny).
3. Cap expansion cycles (max 5).
4. Context truncation for long notes (limit LLM context window usage).
5. Periodic auto-save (30s interval when dirty).
6. Dirty indicator on note title.
7. Keyboard shortcut for save (Cmd/Ctrl+S).
8. Empty states, loading states, error toasts.
9. End-to-end testing.

---

## Phase 2+ Considerations

- **Note templates**: Pre-built templates (meeting notes, to-do list, project plan) the user can start from.
- **Note search**: Full-text search across all notes.
- **Note export**: Download as `.md` or `.pdf`.
- **Note tags/folders**: Organize notes with labels or folders.
- **Chat-to-note extraction**: Select a portion of a chat message and "Send to note" with one click.
- **Collaborative notes**: Real-time multi-user editing (requires WebSocket or CRDT).
- **Voice input**: Microphone-to-text transcription feeding into note-taking mode.
