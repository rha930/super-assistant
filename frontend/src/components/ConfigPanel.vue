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
      <!-- Theme -->
      <div>
        <h3 class="text-sm font-semibold app-text mb-2">Theme</h3>
        <select
          :value="selectedTheme"
          @change="onThemeChange"
          class="w-full px-3 py-2 border app-border rounded-lg text-sm app-surface app-text"
          aria-label="Select theme"
        >
          <option value="light">Light</option>
          <option value="dark">Dark</option>
          <option value="system">System</option>
        </select>
      </div>

      <!-- Model Selection -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-sm font-semibold app-text">Model</h3>
          <button
            @click="refreshModels"
            :disabled="modelsLoading"
            class="p-1 app-text-muted rounded hover:opacity-80 transition-opacity disabled:opacity-40"
            aria-label="Refresh model list"
            title="Refresh model list"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              class="w-4 h-4"
              :class="{ 'animate-spin': modelsLoading }"
            >
              <path d="M17.65 6.35A7.96 7.96 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
            </svg>
          </button>
        </div>

        <!-- Current model badge (always visible) -->
        <div class="inline-flex items-center px-3 py-1 rounded-full app-surface-muted border app-border text-xs font-mono app-text mb-2">
          {{ activeModel }}
        </div>

        <!-- Stale model warning -->
        <div
          v-if="isModelStale"
          class="mb-2 px-3 py-2 text-xs rounded-lg border border-yellow-400 bg-yellow-50 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-700"
        >
          Current model is no longer available. Select another model below.
        </div>

        <!-- Runtime error warning -->
        <div
          v-if="configStore.modelsError"
          class="mb-2 px-3 py-2 text-xs rounded-lg border border-red-300 bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300 dark:border-red-700"
        >
          {{ configStore.modelsError }}
        </div>

        <!-- Model dropdown -->
        <select
          v-model="config.model"
          :disabled="modelsLoading || noModelsAvailable"
          class="w-full px-3 py-2 border app-border rounded-lg text-sm app-surface app-text disabled:opacity-60"
          aria-label="Select model"
        >
          <option v-if="noModelsAvailable" value="" disabled>
            No local models available. Pull a model first.
          </option>
          <option
            v-for="model in configStore.availableModels"
            :key="model"
            :value="model"
          >
            {{ model }}
          </option>
          <!-- Keep stale model visible as an option so the value isn't lost -->
          <option
            v-if="isModelStale && config.model"
            :value="config.model"
            disabled
          >
            {{ config.model }} (unavailable)
          </option>
        </select>
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
        :disabled="isSaving || !canSave"
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
import { useUIStore } from '../stores/uiStore'

defineEmits<{
  close: []
}>()

const configStore = useConfigStore()
const uiStore = useUIStore()
const isSaving = ref(false)

const selectedTheme = computed(() => uiStore.selectedTheme)

const onThemeChange = (event: Event) => {
  const target = event.target as HTMLSelectElement
  if (target.value === 'light' || target.value === 'dark' || target.value === 'system') {
    uiStore.setTheme(target.value)
  }
}

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

const modelsLoading = computed(() => configStore.modelsLoading)

const noModelsAvailable = computed(() =>
  !configStore.modelsLoading && configStore.availableModels.length === 0
)

const isModelStale = computed(() => {
  const model = (config.model || '').trim()
  if (!model) return false
  if (configStore.availableModels.length === 0) return false
  return !configStore.availableModels.includes(model)
})

const canSave = computed(() => {
  const model = (config.model || '').trim()
  if (!model) return false
  if (isModelStale.value) return false
  return true
})

const refreshModels = async () => {
  await configStore.loadAvailableModels()
}

onMounted(async () => {
  await configStore.loadConfig()
  const stored = configStore.getConfig()
  Object.assign(config, stored)
  await configStore.loadAvailableModels()
})

const saveConfig = async () => {
  const model = (config.model || '').trim()
  if (!model) {
    alert('Please select a model before saving.')
    return
  }
  if (configStore.availableModels.length > 0 && !configStore.availableModels.includes(model)) {
    alert('Selected model is no longer available. Please choose another.')
    return
  }

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
