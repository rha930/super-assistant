import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useNotesStore } from '../stores/notesStore'

// Mock the api module
vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

import { api } from '../services/api'
const mockApi = vi.mocked(api)

describe('notesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts with empty notes', () => {
      const store = useNotesStore()
      expect(store.notes).toEqual([])
      expect(store.activeNote).toBeNull()
      expect(store.noteTakingMode).toBe(false)
      expect(store.pendingSuggestion).toBeNull()
      expect(store.isDirty).toBe(false)
    })
  })

  describe('CRUD', () => {
    it('loadNotes populates notes list', async () => {
      const store = useNotesStore()
      mockApi.get.mockResolvedValue({
        data: { data: { notes: [{ id: 'n1', title: 'Test', preview: '', updated_at: '' }] } },
      })
      await store.loadNotes()
      expect(store.notes).toHaveLength(1)
      expect(store.notes[0].title).toBe('Test')
    })

    it('createNote calls API and reloads list', async () => {
      const store = useNotesStore()
      const note = { id: 'n1', user_id: 'u1', title: 'New', content: '', created_at: '', updated_at: '' }
      mockApi.post.mockResolvedValue({ data: { data: { note } } })
      mockApi.get.mockResolvedValue({ data: { data: { notes: [] } } })

      const result = await store.createNote('New')
      expect(result.id).toBe('n1')
      expect(mockApi.post).toHaveBeenCalledWith('/api/notes', { title: 'New' })
    })

    it('deleteNote removes active note and exits note-taking mode', async () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'T', content: '', created_at: '', updated_at: '' }
      store.noteTakingMode = true
      mockApi.delete.mockResolvedValue({})
      mockApi.get.mockResolvedValue({ data: { data: { notes: [] } } })

      await store.deleteNote('n1')
      expect(store.activeNote).toBeNull()
      expect(store.noteTakingMode).toBe(false)
    })

    it('updateTitle marks dirty', () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'Old', content: '', created_at: '', updated_at: '' }
      store.updateTitle('New')
      expect(store.activeNote?.title).toBe('New')
      expect(store.isDirty).toBe(true)
    })

    it('updateContent marks dirty', () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'T', content: '', created_at: '', updated_at: '' }
      store.updateContent('new content')
      expect(store.activeNote?.content).toBe('new content')
      expect(store.isDirty).toBe(true)
    })
  })

  describe('note-taking mode', () => {
    it('enterNoteTakingMode with existing note sets flag', async () => {
      const store = useNotesStore()
      const note = { id: 'n1', user_id: 'u1', title: 'T', content: '', created_at: '', updated_at: '' }
      mockApi.get.mockResolvedValue({ data: { data: { note } } })

      await store.enterNoteTakingMode('n1')
      expect(store.noteTakingMode).toBe(true)
      expect(store.activeNote?.id).toBe('n1')
    })

    it('enterNoteTakingMode without note creates one', async () => {
      const store = useNotesStore()
      const note = { id: 'n2', user_id: 'u1', title: 'Auto', content: '', created_at: '', updated_at: '' }
      mockApi.post.mockResolvedValue({ data: { data: { note } } })
      mockApi.get.mockResolvedValue({ data: { data: { notes: [] } } })

      await store.enterNoteTakingMode()
      expect(store.noteTakingMode).toBe(true)
      expect(store.activeNote?.id).toBe('n2')
    })

    it('exitNoteTakingMode clears state', () => {
      const store = useNotesStore()
      store.noteTakingMode = true
      store.pendingSuggestion = { suggestion: 'x', original_input: 'y', noteId: 'n1' }
      store.exitNoteTakingMode()
      expect(store.noteTakingMode).toBe(false)
      expect(store.pendingSuggestion).toBeNull()
    })
  })

  describe('expand / accept / deny', () => {
    it('expandInput sets pending suggestion', async () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'T', content: '', created_at: '', updated_at: '' }
      mockApi.post.mockResolvedValue({
        data: { data: { suggestion: '## Grocery List\n- Milk', original_input: 'grocery list' } },
      })

      await store.expandInput('grocery list')
      expect(store.pendingSuggestion).not.toBeNull()
      expect(store.pendingSuggestion?.suggestion).toContain('Grocery List')
      expect(store.pendingSuggestion?.original_input).toBe('grocery list')
    })

    it('acceptSuggestion appends to note and clears pending', async () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'My Note', content: '', created_at: '', updated_at: '' }
      store.pendingSuggestion = { suggestion: 'expanded', original_input: 'raw', noteId: 'n1' }

      const updatedNote = { id: 'n1', user_id: 'u1', title: 'My Note', content: 'expanded', created_at: '', updated_at: '' }
      mockApi.patch.mockResolvedValue({ data: { data: { note: updatedNote } } })
      mockApi.get.mockResolvedValue({ data: { data: { notes: [] } } })

      const result = await store.acceptSuggestion()
      expect(result).toContain('My Note')
      expect(store.pendingSuggestion).toBeNull()
      expect(store.activeNote?.content).toBe('expanded')
    })

    it('denySuggestion appends original input', async () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'T', content: '', created_at: '', updated_at: '' }
      store.pendingSuggestion = { suggestion: 'expanded', original_input: 'raw text', noteId: 'n1' }

      const updatedNote = { id: 'n1', user_id: 'u1', title: 'T', content: 'raw text', created_at: '', updated_at: '' }
      mockApi.patch.mockResolvedValue({ data: { data: { note: updatedNote } } })
      mockApi.get.mockResolvedValue({ data: { data: { notes: [] } } })

      const result = await store.denySuggestion()
      expect(result).toContain('Original text')
      expect(store.pendingSuggestion).toBeNull()
    })

    it('expandMore increments count and replaces suggestion', async () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'T', content: '', created_at: '', updated_at: '' }
      store.pendingSuggestion = { suggestion: 'v1', original_input: 'raw', noteId: 'n1' }

      mockApi.post.mockResolvedValue({
        data: { data: { suggestion: 'v2 with more detail' } },
      })

      await store.expandMore()
      expect(store.expandCount).toBe(1)
      expect(store.pendingSuggestion?.suggestion).toBe('v2 with more detail')
    })

    it('expandMore returns null at max expansions', async () => {
      const store = useNotesStore()
      store.activeNote = { id: 'n1', user_id: 'u1', title: 'T', content: '', created_at: '', updated_at: '' }
      store.pendingSuggestion = { suggestion: 'v1', original_input: 'raw', noteId: 'n1' }
      store.expandCount = store.maxExpansions

      const result = await store.expandMore()
      expect(result).toBeNull()
    })
  })

  describe('shortcut keys', () => {
    it('returns null when no pending suggestion', () => {
      const store = useNotesStore()
      expect(store.getShortcutAction('a')).toBeNull()
    })

    it('returns accept for "a"', () => {
      const store = useNotesStore()
      store.pendingSuggestion = { suggestion: 'x', original_input: 'y', noteId: 'n1' }
      expect(store.getShortcutAction('a')).toBe('accept')
      expect(store.getShortcutAction('A')).toBe('accept')
      expect(store.getShortcutAction(' a ')).toBe('accept')
    })

    it('returns deny for "d"', () => {
      const store = useNotesStore()
      store.pendingSuggestion = { suggestion: 'x', original_input: 'y', noteId: 'n1' }
      expect(store.getShortcutAction('d')).toBe('deny')
    })

    it('returns expand for "e"', () => {
      const store = useNotesStore()
      store.pendingSuggestion = { suggestion: 'x', original_input: 'y', noteId: 'n1' }
      expect(store.getShortcutAction('e')).toBe('expand')
    })

    it('returns null for longer text containing shortcut letters', () => {
      const store = useNotesStore()
      store.pendingSuggestion = { suggestion: 'x', original_input: 'y', noteId: 'n1' }
      expect(store.getShortcutAction('accept')).toBeNull()
      expect(store.getShortcutAction('add something')).toBeNull()
    })
  })
})
