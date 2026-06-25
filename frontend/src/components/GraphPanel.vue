<template>
  <div class="h-full flex flex-col app-surface border-l app-border">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b app-border">
      <h2 class="text-lg font-semibold app-text">Graphs</h2>
    </div>

    <!-- Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Empty State -->
      <div
        v-if="currentGraphs.length === 0"
        class="flex items-center justify-center h-full app-text-muted"
      >
        <p class="text-center">
          <span class="text-3xl mb-2 block">📊</span>
          No graphs available. Agent responses with data will appear here.
        </p>
      </div>

      <!-- Graph Selector (if multiple graphs) -->
      <div v-if="currentGraphs.length > 1" class="border-b app-border p-3">
        <div class="space-y-2">
          <label class="text-xs font-semibold app-text-muted">Select Graph</label>
          <select
            :value="selectedGraphId"
            @change="selectGraph"
            class="w-full px-3 py-2 rounded border app-border app-surface app-text text-sm"
          >
            <option
              v-for="graph in currentGraphs"
              :key="graph.id"
              :value="graph.id"
            >
              {{ graph.title }}
            </option>
          </select>
        </div>
      </div>

      <!-- Chart Display -->
      <div v-if="selectedGraph" class="flex-1 overflow-auto p-4">
        <div class="mb-2">
          <h3 class="text-sm font-semibold app-text">{{ selectedGraph.title }}</h3>
          <p class="text-xs app-text-muted">{{ selectedGraph.chartType }}</p>
        </div>
        <ChartRenderer :graph="selectedGraph" />
      </div>

      <!-- Error State -->
      <div v-if="hasError" class="flex-1 flex items-center justify-center p-4">
        <div class="text-sm app-text-muted bg-red-50 dark:bg-red-900/20 p-3 rounded text-red-800 dark:text-red-200">
          {{ errorMessage }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '../stores/chatStore'
import ChartRenderer from './ChartRenderer.vue'

const chatStore = useChatStore()

const currentGraphs = computed(() => chatStore.currentGraphs)
const selectedGraphId = computed(() => chatStore.selectedGraphId)
const selectedGraph = computed(() => chatStore.selectedGraph)

const hasError = computed(() => {
  return currentGraphs.value.length === 0 && selectedGraphId.value !== undefined
})

const errorMessage = computed(() => {
  return 'Failed to load graphs. Please try again.'
})

const selectGraph = (event: Event) => {
  const target = event.target as HTMLSelectElement
  if (target.value) {
    chatStore.selectGraph(target.value)
  }
}
</script>

<style scoped>
/* Graph panel specific styles can be added here */
</style>
