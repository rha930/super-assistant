import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const thinkingText = ref('')

  const setLoading = (value: boolean) => {
    isLoading.value = value
  }

  const setError = (err: string | null) => {
    error.value = err
  }

  const clearError = () => {
    error.value = null
  }

  const setThinking = (text: string) => {
    thinkingText.value = text
  }

  const clearThinking = () => {
    thinkingText.value = ''
  }

  return {
    isLoading,
    error,
    thinkingText,
    setLoading,
    setError,
    clearError,
    setThinking,
    clearThinking
  }
})
