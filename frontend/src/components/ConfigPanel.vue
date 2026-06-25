<template>
  <div class="h-full flex flex-col">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b app-border">
      <h2 class="text-lg font-semibold app-text">Configuration</h2>
      <button
        @click="$emit('close')"
        class="app-text-muted hover:app-text text-2xl"
      >
        ✕
      </button>
    </div>

    <!-- Configuration Form -->
    <div class="flex-1 overflow-y-auto p-6 space-y-6">
      <!-- Active Model -->
      <div>
        <h3 class="text-sm font-semibold app-text mb-2">Active Model</h3>
        <div class="inline-flex items-center px-3 py-1 rounded-full app-surface-muted border app-border text-xs font-mono app-text">
          {{ activeModel }}
        </div>
      </div>

      <!-- Model Parameters Section -->
      <div>
        <h3 class="text-sm font-semibold app-text mb-3">Model Parameters</h3>
        <div class="space-y-4">
          <!-- Temperature -->
          <div>
            <label class="block text-xs font-medium app-text-muted mb-1">
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
            <p class="text-xs app-text-muted mt-1">Controls randomness (0 = deterministic, 2 = very random)</p>
          </div>

          <!-- Max Tokens -->
          <div>
            <label class="block text-xs font-medium app-text-muted mb-1">
              Max Tokens
            </label>
            <input
              v-model.number="config.model_parameters.max_tokens"
              type="number"
              min="1"
              max="4000"
              class="w-full px-3 py-2 border app-border rounded-lg text-sm app-surface app-text"
            />
          </div>

          <!-- Top P -->
          <div>
            <label class="block text-xs font-medium app-text-muted mb-1">
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
            <p class="text-xs app-text-muted mt-1">Nucleus sampling (lower = more focused)</p>
          </div>
        </div>
      </div>

      <!-- System Prompt Section -->
      <div>
        <h3 class="text-sm font-semibold app-text mb-3">System Prompt</h3>
        <textarea
          v-model="config.system_prompt"
          placeholder="Enter the system prompt for the agent..."
          rows="8"
          class="w-full px-3 py-2 border app-border rounded-lg text-sm font-mono resize-none app-surface app-text"
        ></textarea>
      </div>

      <!-- Agent Configuration Section -->
      <div>
        <h3 class="text-sm font-semibold app-text mb-3">Agent Settings</h3>
        <div class="space-y-4">
          <!-- Max Iterations -->
          <div>
            <label class="block text-xs font-medium app-text-muted mb-1">
              Max Iterations
            </label>
            <input
              v-model.number="config.agent_config.max_iterations"
              type="number"
              min="1"
              max="100"
              class="w-full px-3 py-2 border app-border rounded-lg text-sm app-surface app-text"
            />
          </div>

          <!-- Timeout -->
          <div>
            <label class="block text-xs font-medium app-text-muted mb-1">
              Timeout (seconds)
            </label>
            <input
              v-model.number="config.agent_config.timeout"
              type="number"
              min="1"
              max="600"
              class="w-full px-3 py-2 border app-border rounded-lg text-sm app-surface app-text"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Footer Buttons -->
    <div class="border-t app-border p-4 space-y-2">
      <button
        @click="saveConfig"
        :disabled="isSaving"
        class="w-full px-4 py-2 btn-primary rounded-lg disabled:opacity-60 transition-colors"
      >
        {{ isSaving ? 'Saving...' : 'Save Configuration' }}
      </button>
      <button
        @click="resetConfig"
        class="w-full px-4 py-2 app-surface-muted app-text rounded-lg hover:opacity-90 transition-opacity"
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
