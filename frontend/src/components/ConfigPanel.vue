<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b border-gray-200">
      <h2 class="text-lg font-semibold text-gray-900">Configuration</h2>
      <button
        @click="$emit('close')"
        class="text-gray-400 hover:text-gray-600 text-2xl"
      >
        ✕
      </button>
    </div>

    <!-- Configuration Form -->
    <div class="flex-1 overflow-y-auto p-6 space-y-6">
      <!-- Active Model -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 mb-2">Active Model</h3>
        <div class="inline-flex items-center px-3 py-1 rounded-full bg-gray-100 border border-gray-200 text-xs font-mono text-gray-800">
          {{ activeModel }}
        </div>
      </div>

      <!-- Model Parameters Section -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 mb-3">Model Parameters</h3>
        <div class="space-y-4">
          <!-- Temperature -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Temperature: {{ config.model_parameters.temperature.toFixed(2) }}
            </label>
            <input
              v-model.number="config.model_parameters.temperature"
              type="range"
              min="0"
              max="2"
              step="0.1"
              class="w-full"
            />
            <p class="text-xs text-gray-500 mt-1">Controls randomness (0 = deterministic, 2 = very random)</p>
          </div>

          <!-- Max Tokens -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Max Tokens
            </label>
            <input
              v-model.number="config.model_parameters.max_tokens"
              type="number"
              min="1"
              max="4000"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          <!-- Top P -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Top P: {{ config.model_parameters.top_p.toFixed(2) }}
            </label>
            <input
              v-model.number="config.model_parameters.top_p"
              type="range"
              min="0"
              max="1"
              step="0.1"
              class="w-full"
            />
            <p class="text-xs text-gray-500 mt-1">Nucleus sampling (lower = more focused)</p>
          </div>
        </div>
      </div>

      <!-- System Prompt Section -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 mb-3">System Prompt</h3>
        <textarea
          v-model="config.system_prompt"
          placeholder="Enter the system prompt for the agent..."
          rows="8"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono resize-none"
        ></textarea>
      </div>

      <!-- Agent Configuration Section -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 mb-3">Agent Settings</h3>
        <div class="space-y-4">
          <!-- Max Iterations -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Max Iterations
            </label>
            <input
              v-model.number="config.agent_config.max_iterations"
              type="number"
              min="1"
              max="100"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          <!-- Timeout -->
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              Timeout (seconds)
            </label>
            <input
              v-model.number="config.agent_config.timeout"
              type="number"
              min="1"
              max="600"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Footer Buttons -->
    <div class="border-t border-gray-200 p-4 space-y-2">
      <button
        @click="saveConfig"
        :disabled="isSaving"
        class="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
      >
        {{ isSaving ? 'Saving...' : 'Save Configuration' }}
      </button>
      <button
        @click="resetConfig"
        class="w-full px-4 py-2 bg-gray-200 text-gray-900 rounded-lg hover:bg-gray-300 transition-colors"
      >
        Reset to Defaults
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useConfigStore } from '../stores/configStore'

defineEmits<{
  close: []
}>()

const configStore = useConfigStore()
const isSaving = ref(false)

const config = reactive({
  model: '',
  model_parameters: {
    temperature: 0.7,
    max_tokens: 1000,
    top_p: 0.9
  },
  system_prompt: '',
  agent_config: {
    max_iterations: 10,
    timeout: 30
  }
})

const activeModel = computed(() => {
  const value = (config.model || '').trim()
  return value || 'No active model configured'
})

onMounted(async () => {
  await configStore.loadConfig()
  const stored = configStore.getConfig()
  Object.assign(config, stored)
})

const saveConfig = async () => {
  isSaving.value = true
  try {
    await configStore.saveConfig(config)
    alert('Configuration saved!')
  } catch (error) {
    alert('Failed to save configuration')
    console.error(error)
  } finally {
    isSaving.value = false
  }
}

const resetConfig = () => {
  if (confirm('Reset to default configuration?')) {
    configStore.resetConfig()
    const defaults = configStore.getConfig()
    Object.assign(config, defaults)
  }
}
</script>
