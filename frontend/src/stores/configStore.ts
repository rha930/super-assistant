import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../services/api'

interface Config {
  model: string
  model_parameters: {
    temperature: number
    max_tokens: number
    top_p: number
  }
  system_prompt: string
  agent_config: {
    max_iterations: number
    timeout: number
  }
}

const DEFAULT_CONFIG: Config = {
  model: '',
  model_parameters: {
    temperature: 0.7,
    max_tokens: 1000,
    top_p: 0.9
  },
  system_prompt: 'You are a helpful AI assistant powered by AWS Strands Agent.',
  agent_config: {
    max_iterations: 10,
    timeout: 30
  }
}

export const useConfigStore = defineStore('config', () => {
  const config = ref<Config>(DEFAULT_CONFIG)
  const availableModels = ref<string[]>([])
  const modelsLoading = ref(false)
  const modelsError = ref<string | null>(null)

  const getConfig = (): Config => {
    return config.value
  }

  const loadAvailableModels = async () => {
    modelsLoading.value = true
    modelsError.value = null
    try {
      const response = await api.get('/api/models')
      availableModels.value = response.data?.data?.models || []
    } catch (error: any) {
      const msg = error?.response?.data?.message || 'Failed to load models'
      modelsError.value = msg
      console.error('Failed to load available models:', error)
    } finally {
      modelsLoading.value = false
    }
  }

  const saveConfig = async (newConfig: Config) => {
    try {
      await api.post('/api/config', newConfig)
      config.value = newConfig
    } catch (error) {
      console.error('Failed to save config:', error)
      throw error
    }
  }

  const loadConfig = async () => {
    try {
      const response = await api.get('/api/config')
      config.value = response.data?.data || DEFAULT_CONFIG
    } catch (error) {
      console.error('Failed to load config:', error)
    }
  }

  const resetConfig = () => {
    config.value = DEFAULT_CONFIG
  }

  return {
    config,
    availableModels,
    modelsLoading,
    modelsError,
    getConfig,
    loadAvailableModels,
    saveConfig,
    loadConfig,
    resetConfig
  }
})
