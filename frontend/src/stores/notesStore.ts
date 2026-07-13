import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Note, NoteSummary, NoteSuggestion } from '../types/note'
import { api } from '../services/api'

export const useNotesStore = defineStore('notes', () => {
  const notes = ref<NoteSummary[]>([])
  const activeNote = ref<Note | null>(null)
  const noteTakingMode = ref(false)
  const pendingSuggestion = ref<NoteSuggestion | null>(null)
  const isExpanding = ref(false)
  const isDirty = ref(false)
  const expandCount = ref(0)
  const maxExpansions = 5

  // ------------------------------------------------------------------
  // CRUD
  // ------------------------------------------------------------------

  async function loadNotes() {
    try {
      const response = await api.get('/api/notes')
      notes.value = response.data?.data?.notes || []
    } catch (error) {
      console.error('Failed to load notes:', error)
    }
  }

  async function createNote(title?: string): Promise<Note> {
    const response = await api.post('/api/notes', { title: title || 'Untitled Note' })
    const note: Note = response.data?.data?.note
    await loadNotes()
    return note
  }

  async function openNote(noteId: string) {
    try {
      const response = await api.get(`/api/notes/${noteId}`)
      activeNote.value = response.data?.data?.note || null
      isDirty.value = false
    } catch (error) {
      console.error('Failed to open note:', error)
    }
  }

  async function saveNote() {
    if (!activeNote.value || !isDirty.value) return
    try {
      const response = await api.put(`/api/notes/${activeNote.value.id}`, {
        title: activeNote.value.title,
        content: activeNote.value.content,
      })
      activeNote.value = response.data?.data?.note || activeNote.value
      isDirty.value = false
      await loadNotes()
    } catch (error) {
      console.error('Failed to save note:', error)
    }
  }

  async function deleteNote(noteId: string) {
    try {
      await api.delete(`/api/notes/${noteId}`)
      if (activeNote.value?.id === noteId) {
        activeNote.value = null
        exitNoteTakingMode()
      }
      await loadNotes()
    } catch (error) {
      console.error('Failed to delete note:', error)
    }
  }

  function updateTitle(title: string) {
    if (activeNote.value) {
      activeNote.value = { ...activeNote.value, title }
      isDirty.value = true
    }
  }

  function updateContent(content: string) {
    if (activeNote.value) {
      activeNote.value = { ...activeNote.value, content }
      isDirty.value = true
    }
  }

  function closeNote() {
    activeNote.value = null
    isDirty.value = false
  }

  // ------------------------------------------------------------------
  // Note-taking mode
  // ------------------------------------------------------------------

  async function enterNoteTakingMode(noteId?: string) {
    if (noteId) {
      await openNote(noteId)
    } else if (!activeNote.value) {
      const now = new Date().toLocaleString()
      const note = await createNote(`Note — ${now}`)
      activeNote.value = note
    }
    noteTakingMode.value = true
    expandCount.value = 0
  }

  function exitNoteTakingMode() {
    noteTakingMode.value = false
    pendingSuggestion.value = null
    expandCount.value = 0
  }

  async function expandInput(input: string): Promise<string> {
    if (!activeNote.value) throw new Error('No active note')
    isExpanding.value = true
    expandCount.value = 0
    try {
      const response = await api.post('/api/notes/expand', {
        input,
        existing_content: activeNote.value.content,
      })
      const data = response.data?.data
      pendingSuggestion.value = {
        suggestion: data.suggestion,
        original_input: data.original_input,
        noteId: activeNote.value.id,
      }
      return data.suggestion
    } finally {
      isExpanding.value = false
    }
  }

  async function acceptSuggestion(): Promise<string | null> {
    if (!pendingSuggestion.value || !activeNote.value) return null
    const { suggestion, noteId } = pendingSuggestion.value
    try {
      const response = await api.patch(`/api/notes/${noteId}/append`, {
        content: suggestion,
      })
      const note = response.data?.data?.note
      if (note) activeNote.value = note
      isDirty.value = false
      const title = activeNote.value?.title || 'note'
      pendingSuggestion.value = null
      expandCount.value = 0
      await loadNotes()
      return `Added to note: ${title}`
    } catch (error) {
      console.error('Failed to accept suggestion:', error)
      return null
    }
  }

  async function denySuggestion(): Promise<string | null> {
    if (!pendingSuggestion.value || !activeNote.value) return null
    const { original_input, noteId } = pendingSuggestion.value
    try {
      const response = await api.patch(`/api/notes/${noteId}/append`, {
        content: original_input,
      })
      const note = response.data?.data?.note
      if (note) activeNote.value = note
      isDirty.value = false
      const title = activeNote.value?.title || 'note'
      pendingSuggestion.value = null
      expandCount.value = 0
      await loadNotes()
      return `Original text added to note: ${title}`
    } catch (error) {
      console.error('Failed to deny suggestion:', error)
      return null
    }
  }

  async function expandMore(): Promise<string | null> {
    if (!pendingSuggestion.value || !activeNote.value) return null
    if (expandCount.value >= maxExpansions) return null
    isExpanding.value = true
    try {
      const response = await api.post('/api/notes/expand-more', {
        previous_suggestion: pendingSuggestion.value.suggestion,
        existing_content: activeNote.value.content,
      })
      const data = response.data?.data
      pendingSuggestion.value = {
        ...pendingSuggestion.value,
        suggestion: data.suggestion,
      }
      expandCount.value++
      return data.suggestion
    } finally {
      isExpanding.value = false
    }
  }

  /**
   * Check if a chat input is a shortcut key for an active suggestion.
   * Returns the action name or null.
   */
  function getShortcutAction(input: string): 'accept' | 'deny' | 'expand' | null {
    if (!pendingSuggestion.value) return null
    const trimmed = input.trim().toLowerCase()
    if (trimmed === 'a') return 'accept'
    if (trimmed === 'd') return 'deny'
    if (trimmed === 'e') return 'expand'
    return null
  }

  return {
    notes,
    activeNote,
    noteTakingMode,
    pendingSuggestion,
    isExpanding,
    isDirty,
    expandCount,
    maxExpansions,
    loadNotes,
    createNote,
    openNote,
    saveNote,
    deleteNote,
    updateTitle,
    updateContent,
    closeNote,
    enterNoteTakingMode,
    exitNoteTakingMode,
    expandInput,
    acceptSuggestion,
    denySuggestion,
    expandMore,
    getShortcutAction,
  }
})
