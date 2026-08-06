<template>
  <nav class="flex flex-col items-center py-3 gap-1 app-surface border-r app-border w-14 shrink-0">
    <button
      v-for="item in items"
      :key="item.module"
      @click="navStore.selectModule(item.module)"
      :aria-label="item.label"
      :title="item.label"
      :aria-pressed="navStore.activeModule === item.module"
      :class="[
        'p-2 rounded-lg transition-colors w-10 h-10 flex items-center justify-center',
        navStore.activeModule === item.module
          ? 'bg-blue-600 text-white'
          : 'app-text-muted hover:opacity-80'
      ]"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        class="w-6 h-6"
        v-html="item.icon"
      ></svg>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { useNavStore } from '../stores/navStore'
import type { NavModule } from '../stores/navStore'

const navStore = useNavStore()

const items: { module: NavModule; label: string; icon: string }[] = [
  {
    module: 'graph',
    label: 'Toggle graphs',
    icon: '<path d="M3 3h2v14h16v2H3z"></path><path d="M7 10h2v7H7z"></path><path d="M12 7h2v10h-2z"></path><path d="M17 5h2v12h-2z"></path>',
  },
  {
    module: 'notes',
    label: 'Notes',
    icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"></path><path d="M14 2v6h6"></path><path d="M16 13H8M16 17H8M10 9H8" stroke="currentColor" stroke-width="1" fill="none"></path>',
  },
  {
    module: 'map',
    label: 'Map',
    icon: '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5z"/>',
  },
]
</script>
