<template>
  <div id="app" class="h-screen flex flex-col app-bg app-text">
    <!-- Header -->
    <header class="app-surface border-b app-border px-6 py-4 shadow-sm">
      <div class="w-full flex items-center justify-between">
        <h1 class="text-2xl font-bold text-left">Super Agent</h1>
        <div class="flex items-center gap-3">
          <label for="theme-select" class="text-sm font-medium app-text-muted">Theme</label>
          <select
            id="theme-select"
            :value="selectedTheme"
            @change="onThemeChange"
            class="theme-select px-3 py-2 rounded-lg border text-sm app-surface app-border app-text"
            aria-label="Select theme"
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
            <option value="system">System</option>
          </select>

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
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import ConfigPanel from './components/ConfigPanel.vue'
import GraphPanel from './components/GraphPanel.vue'
import { useUIStore } from './stores/uiStore'
import { useChatStore } from './stores/chatStore'

const showConfigPanel = ref(false)
const showGraphPanel = ref(false)
const graphPanelWidth = ref(384)
const uiStore = useUIStore()
const chatStore = useChatStore()

const selectedTheme = computed(() => uiStore.selectedTheme)

const toggleConfigPanel = () => {
  showConfigPanel.value = !showConfigPanel.value
}

const toggleGraphPanel = () => {
  showGraphPanel.value = !showGraphPanel.value
}

const onThemeChange = (event: Event) => {
  const target = event.target as HTMLSelectElement
  if (target.value === 'light' || target.value === 'dark' || target.value === 'system') {
    uiStore.setTheme(target.value)
  }
}

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
