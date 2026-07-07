<template>
  <!-- Auth check loading -->
  <div v-if="authLoading" class="h-screen flex items-center justify-center app-bg app-text">
    <p class="app-text-muted">Loading...</p>
  </div>

  <!-- Login page when not authenticated -->
  <LoginPage v-else-if="!isAuthenticated" />

  <!-- Main app when authenticated -->
  <div v-else id="app" class="h-screen flex flex-col app-bg app-text">
    <!-- Header -->
    <header class="app-surface border-b app-border px-6 py-4 shadow-sm">
      <div class="w-full flex items-center justify-between">
        <h1 class="text-2xl font-bold text-left">Super Agent</h1>
        <div class="flex items-center gap-3">
          <span class="text-sm app-text-muted hidden sm:inline">{{ displayName }}</span>

          <button
            @click="toggleGraphPanel"
            class="p-2 app-text-muted rounded-lg transition-opacity hover:opacity-80"
            aria-label="Toggle graph panel"
            title="Toggle graphs"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
              <path d="M3 3h2v14h16v2H3z"></path>
              <path d="M7 10h2v7H7z"></path>
              <path d="M12 7h2v10h-2z"></path>
              <path d="M17 5h2v12h-2z"></path>
            </svg>
          </button>

          <button
            @click="toggleNotesPanel"
            :class="[
              'p-2 rounded-lg transition-opacity hover:opacity-80',
              notesStore.noteTakingMode ? 'text-green-500' : 'app-text-muted'
            ]"
            aria-label="Toggle notes panel"
            title="Notes"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"></path>
              <path d="M14 2v6h6"></path>
              <path d="M16 13H8M16 17H8M10 9H8" stroke="currentColor" stroke-width="1" fill="none"></path>
            </svg>
          </button>

          <button
            @click="toggleHistoryPanel"
            class="p-2 app-text-muted rounded-lg transition-opacity hover:opacity-80"
            aria-label="Toggle history panel"
            title="Chat history"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
              <path d="M13 3a9 9 0 1 0 8.95 10h-2.02A7 7 0 1 1 13 5v3l4-4-4-4v3z"></path>
              <path d="M12 8h2v5h-2z"></path>
              <path d="M12 14h5v2h-5z"></path>
            </svg>
          </button>

          <button
            @click="toggleConfigPanel"
            class="p-2 app-text-muted rounded-lg transition-opacity hover:opacity-80"
            aria-label="Open configuration"
            title="Configuration"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
              <rect x="4" y="6" width="16" height="2" rx="1"></rect>
              <rect x="4" y="11" width="16" height="2" rx="1"></rect>
              <rect x="4" y="16" width="16" height="2" rx="1"></rect>
            </svg>
          </button>

          <button
            @click="handleLogout"
            class="p-2 app-text-muted rounded-lg transition-opacity hover:opacity-80"
            aria-label="Log out"
            title="Log out"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="w-6 h-6">
              <path d="M5 5h7V3H3v18h9v-2H5z"></path>
              <path d="M21 12l-4-4v3H9v2h8v3z"></path>
            </svg>
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 flex overflow-hidden">
      <!-- Chat Window -->
      <div class="flex-1 flex flex-col min-w-0">
        <ChatWindow />
      </div>

      <!-- Graph Panel (Resizable) -->
      <aside
        v-if="showGraphPanel"
        :style="{ width: graphPanelWidth + 'px' }"
        class="flex flex-col min-w-0 transition-[width]"
      >
        <div
          class="w-1 h-full cursor-col-resize app-surface-muted hover:app-surface transition-colors"
          @mousedown="startResizeGraphPanel"
          title="Drag to resize"
        ></div>
        <GraphPanel />
      </aside>

      <!-- Config Panel (Sidebar) -->
      <aside
        v-if="showConfigPanel"
        class="w-96 flex flex-col min-w-0"
      >
        <ConfigPanel @close="toggleConfigPanel" />
      </aside>

      <!-- History Panel -->
      <aside
        v-if="showHistoryPanel"
        class="w-96 flex flex-col min-w-0"
      >
        <HistoryPanel />
      </aside>

      <!-- Notes Panel -->
      <aside
        v-if="showNotesPanel"
        class="w-96 flex flex-col min-w-0"
      >
        <NotesPanel />
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import ConfigPanel from './components/ConfigPanel.vue'
import GraphPanel from './components/GraphPanel.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import LoginPage from './components/LoginPage.vue'
import NotesPanel from './components/NotesPanel.vue'
import { useChatStore } from './stores/chatStore'
import { useAuthStore } from './stores/authStore'
import { useNotesStore } from './stores/notesStore'

const showConfigPanel = ref(false)
const showGraphPanel = ref(false)
const showHistoryPanel = ref(false)
const showNotesPanel = ref(false)
const graphPanelWidth = ref(384)
const chatStore = useChatStore()
const authStore = useAuthStore()
const notesStore = useNotesStore()

const isAuthenticated = computed(() => authStore.isAuthenticated)
const authLoading = computed(() => authStore.loading)
const displayName = computed(() => authStore.user?.display_name || authStore.user?.username || '')

const toggleConfigPanel = () => {
  showConfigPanel.value = !showConfigPanel.value
}

const toggleGraphPanel = () => {
  showGraphPanel.value = !showGraphPanel.value
}

const toggleHistoryPanel = () => {
  showHistoryPanel.value = !showHistoryPanel.value
}

const toggleNotesPanel = () => {
  showNotesPanel.value = !showNotesPanel.value
  if (!showNotesPanel.value) {
    notesStore.exitNoteTakingMode()
  }
}

const handleLogout = () => {
  authStore.logout()
}

onMounted(async () => {
  await authStore.checkAuth()
})

watch(
  () => chatStore.currentGraphs.length,
  (count, prevCount) => {
    if (count > 0 && count !== prevCount) {
      showGraphPanel.value = true
    }
  }
)

const startResizeGraphPanel = (e: MouseEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = graphPanelWidth.value

  const handleMouseMove = (moveEvent: MouseEvent) => {
    const delta = startX - moveEvent.clientX
    const newWidth = Math.max(300, Math.min(800, startWidth + delta))
    graphPanelWidth.value = newWidth
  }

  const handleMouseUp = () => {
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }

  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
}

#app {
  font-family: 'Avenir Next', 'Segoe UI', 'Roboto', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.theme-select:focus {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

/* Smooth resize behavior */
main {
  transition: none;
}
</style>
