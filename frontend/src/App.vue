<template>
  <!-- Auth check loading -->
  <div v-if="authLoading" class="h-screen flex items-center justify-center app-bg app-text">
    <p class="app-text-muted">Loading...</p>
  </div>

  <!-- Login page when not authenticated -->
  <LoginPage v-else-if="!isAuthenticated" />

  <!-- Main app when authenticated -->
  <div v-else id="app" class="h-screen flex flex-col app-bg app-text">
    <!-- Header: title + account controls only (no module toggles) -->
    <header class="app-surface border-b app-border px-6 py-4 shadow-sm">
      <div class="w-full flex items-center justify-between">
        <h1 class="text-2xl font-bold text-left">AERIAL</h1>
        <div class="flex items-center gap-3">
          <span class="text-sm app-text-muted hidden sm:inline">{{ displayName }}</span>

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
      <!-- Left sidebar: fixed nav rail + resizable content panel -->
      <div class="flex shrink-0 z-10" :class="navStore.activeModule ? 'shadow-xl' : ''">
        <NavBar />

        <!-- Active module panel -->
        <aside
          v-if="navStore.activeModule === 'graph'"
          :style="{ width: graphPanelWidth + 'px' }"
          class="flex min-w-0 transition-[width]"
        >
          <div class="flex flex-col flex-1 min-w-0">
            <GraphPanel />
          </div>
          <div
            class="w-1.5 h-full cursor-col-resize bg-blue-500/20 hover:bg-blue-500/50 transition-colors shrink-0"
            @mousedown="startResizeGraphPanel"
            title="Drag to resize"
          ></div>
        </aside>

        <aside
          v-else-if="navStore.activeModule === 'notes'"
          :style="{ width: notesPanelWidth + 'px' }"
          class="flex min-w-0 transition-[width]"
        >
          <div class="flex flex-col flex-1 min-w-0">
            <NotesPanel />
          </div>
          <div
            class="w-1.5 h-full cursor-col-resize bg-blue-500/20 hover:bg-blue-500/50 transition-colors shrink-0"
            @mousedown="startResizeNotesPanel"
            title="Drag to resize"
          ></div>
        </aside>

        <aside
          v-else-if="navStore.activeModule === 'map'"
          :style="{ width: mapPanelWidth + 'px' }"
          class="flex min-w-0 transition-[width]"
        >
          <div class="flex flex-col flex-1 min-w-0">
            <MapPanel />
          </div>
          <div
            class="w-1.5 h-full cursor-col-resize bg-blue-500/20 hover:bg-blue-500/50 transition-colors shrink-0"
            @mousedown="startResizeMapPanel"
            title="Drag to resize"
          ></div>
        </aside>
      </div>

      <!-- Chat Window fills remaining space -->
      <div class="flex-1 flex flex-col min-w-0">
        <ChatWindow />
      </div>

      <!-- History Panel — header-launched, right side, resizable -->
      <aside
        v-if="showHistoryPanel"
        :style="{ width: historyPanelWidth + 'px' }"
        class="flex flex-col min-w-0 transition-[width]"
      >
        <div
          class="w-1 h-full cursor-col-resize app-surface-muted hover:app-surface transition-colors shrink-0"
          @mousedown="startResizeHistoryPanel"
          title="Drag to resize"
        ></div>
        <HistoryPanel />
      </aside>

      <!-- Config Panel — stays on right, independent of nav bar -->
      <aside
        v-if="showConfigPanel"
        class="w-96 flex flex-col min-w-0"
      >
        <ConfigPanel @close="toggleConfigPanel" />
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
import MapPanel from './components/MapPanel.vue'
import NavBar from './components/NavBar.vue'
import NotesPanel from './components/NotesPanel.vue'
import { useChatStore } from './stores/chatStore'
import { useAuthStore } from './stores/authStore'
import { useNavStore } from './stores/navStore'
import { useNotesStore } from './stores/notesStore'

const showConfigPanel = ref(false)
const showHistoryPanel = ref(false)
const graphPanelWidth = ref(384)
const notesPanelWidth = ref(384)
const historyPanelWidth = ref(384)
const mapPanelWidth = ref(384)

const chatStore = useChatStore()
const authStore = useAuthStore()
const navStore = useNavStore()
const notesStore = useNotesStore()

const isAuthenticated = computed(() => authStore.isAuthenticated)
const authLoading = computed(() => authStore.loading)
const displayName = computed(() => authStore.user?.display_name || authStore.user?.username || '')

const toggleConfigPanel = () => {
  showConfigPanel.value = !showConfigPanel.value
}

const toggleHistoryPanel = () => {
  showHistoryPanel.value = !showHistoryPanel.value
}

const handleLogout = () => {
  authStore.logout()
}

onMounted(async () => {
  await authStore.checkAuth()
})

// Auto-open Graph panel when new graphs arrive from the agent
watch(
  () => chatStore.currentGraphs.length,
  (count, prevCount) => {
    if (count > 0 && count !== prevCount && navStore.activeModule !== 'graph') {
      navStore.selectModule('graph')
    }
  }
)

const startResizeGraphPanel = (e: MouseEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = graphPanelWidth.value

  const handleMouseMove = (moveEvent: MouseEvent) => {
    // Panel is left-of-chat: dragging handle right expands width
    const delta = moveEvent.clientX - startX
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

const startResizeNotesPanel = (e: MouseEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = notesPanelWidth.value

  const handleMouseMove = (moveEvent: MouseEvent) => {
    const delta = moveEvent.clientX - startX
    const newWidth = Math.max(300, Math.min(800, startWidth + delta))
    notesPanelWidth.value = newWidth
  }

  const handleMouseUp = () => {
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }

  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

const startResizeMapPanel = (e: MouseEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = mapPanelWidth.value

  const handleMouseMove = (moveEvent: MouseEvent) => {
    const delta = moveEvent.clientX - startX
    const newWidth = Math.max(300, Math.min(800, startWidth + delta))
    mapPanelWidth.value = newWidth
  }

  const handleMouseUp = () => {
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }

  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

const startResizeHistoryPanel = (e: MouseEvent) => {
  e.preventDefault()
  const startX = e.clientX
  const startWidth = historyPanelWidth.value

  const handleMouseMove = (moveEvent: MouseEvent) => {
    // Panel is right-of-chat: dragging handle left expands width
    const delta = startX - moveEvent.clientX
    const newWidth = Math.max(300, Math.min(800, startWidth + delta))
    historyPanelWidth.value = newWidth
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
</style>
