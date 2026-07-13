<template>
  <div class="flex flex-col h-full app-surface border-l app-border">
    <!-- Header -->
    <div class="px-4 py-3 border-b app-border flex items-center justify-between">
      <div class="flex items-center gap-2">
        <button
          v-if="activeNote"
          @click="backToList"
          class="p-1 app-text-muted hover:opacity-80 transition-opacity"
          title="Back to notes"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
            <path fill-rule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clip-rule="evenodd" />
          </svg>
        </button>
        <h2 class="text-lg font-semibold app-text">{{ activeNote ? 'Edit Note' : 'Notes' }}</h2>
        <span v-if="isDirty" class="w-2 h-2 rounded-full bg-yellow-500" title="Unsaved changes"></span>
      </div>
      <div class="flex items-center gap-2">
        <button
          v-if="activeNote"
          @click="toggleNoteTakingMode"
          :class="[
            'px-2 py-1 text-xs rounded-md transition-colors font-medium',
            noteTakingMode
              ? 'bg-green-600 text-white'
              : 'app-surface-muted app-text-muted hover:opacity-80'
          ]"
          :title="noteTakingMode ? 'Exit note-taking mode' : 'Enter note-taking mode'"
        >
          {{ noteTakingMode ? '📝 Active' : '📝 Note Mode' }}
        </button>
        <button
          v-if="!activeNote"
          @click="handleCreateNote"
          class="px-3 py-1 text-sm btn-primary rounded-md"
        >
          + New
        </button>
      </div>
    </div>

    <!-- Note List View -->
    <div v-if="!activeNote" class="flex-1 overflow-y-auto">
      <div v-if="notes.length === 0" class="flex items-center justify-center h-full app-text-muted p-6">
        <p class="text-center">
          <span class="text-3xl mb-2 block">📝</span>
          No notes yet. Create your first note!
        </p>
      </div>
      <div v-else class="divide-y app-border">
        <div
          v-for="note in notes"
          :key="note.id"
          class="px-4 py-3 cursor-pointer hover:opacity-80 transition-opacity group flex items-start justify-between"
          @click="handleOpenNote(note.id)"
        >
          <div class="min-w-0 flex-1">
            <div class="font-medium app-text text-sm truncate">{{ note.title }}</div>
            <div class="text-xs app-text-muted mt-0.5 truncate">{{ note.preview || 'Empty note' }}</div>
            <div class="text-xs app-text-muted mt-0.5">{{ formatDate(note.updated_at) }}</div>
          </div>
          <button
            @click.stop="handleDeleteNote(note.id)"
            class="p-1 app-text-muted opacity-0 group-hover:opacity-100 hover:text-red-500 transition-all"
            title="Delete note"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
              <path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Note Editor View -->
    <NoteEditor
      v-if="activeNote"
      :note="activeNote"
      @update:title="notesStore.updateTitle($event)"
      @update:content="notesStore.updateContent($event)"
      @save="notesStore.saveNote()"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useNotesStore } from '../stores/notesStore'
import NoteEditor from './NoteEditor.vue'

const notesStore = useNotesStore()

const notes = computed(() => notesStore.notes)
const activeNote = computed(() => notesStore.activeNote)
const noteTakingMode = computed(() => notesStore.noteTakingMode)
const isDirty = computed(() => notesStore.isDirty)

onMounted(() => {
  notesStore.loadNotes()
})

async function handleCreateNote() {
  const note = await notesStore.createNote()
  notesStore.activeNote = note
}

async function handleOpenNote(noteId: string) {
  await notesStore.openNote(noteId)
}

function handleDeleteNote(noteId: string) {
  if (confirm('Delete this note? This cannot be undone.')) {
    notesStore.deleteNote(noteId)
  }
}

function backToList() {
  if (notesStore.isDirty) {
    notesStore.saveNote()
  }
  notesStore.closeNote()
  notesStore.exitNoteTakingMode()
}

function toggleNoteTakingMode() {
  if (noteTakingMode.value) {
    notesStore.exitNoteTakingMode()
  } else {
    notesStore.enterNoteTakingMode(activeNote.value?.id)
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>
