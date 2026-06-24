<template>
  <div id="app" class="h-screen flex flex-col bg-gray-50">
    <!-- Header -->
    <header class="bg-white border-b border-gray-200 px-6 py-4 shadow-sm">
      <div class="w-full flex items-center justify-between">
        <h1 class="text-2xl font-bold text-gray-900 text-left">Super Agent</h1>
        <button
          @click="toggleConfigPanel"
          class="p-2 text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
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
    </header>

    <!-- Main Content -->
    <main class="flex-1 flex overflow-hidden">
      <!-- Chat Window -->
      <div class="flex-1 flex flex-col">
        <ChatWindow />
      </div>

      <!-- Config Panel (Sidebar) -->
      <aside
        v-if="showConfigPanel"
        class="w-96 bg-white border-l border-gray-200 shadow-lg flex flex-col"
      >
        <ConfigPanel @close="toggleConfigPanel" />
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import ConfigPanel from './components/ConfigPanel.vue'

const showConfigPanel = ref(false)

const toggleConfigPanel = () => {
  showConfigPanel.value = !showConfigPanel.value
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
}

#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
</style>
