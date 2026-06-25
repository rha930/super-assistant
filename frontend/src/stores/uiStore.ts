import { defineStore } from 'pinia'
import { ref } from 'vue'

type ThemeMode = 'light' | 'dark' | 'system'

const THEME_STORAGE_KEY = 'ui.theme'

export const useUIStore = defineStore('ui', () => {
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const thinkingText = ref('')
  const selectedTheme = ref<ThemeMode>('system')
  const resolvedTheme = ref<'light' | 'dark'>('light')

  let mediaQuery: MediaQueryList | null = null

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

  const getSystemTheme = (): 'light' | 'dark' => {
    if (typeof window === 'undefined') return 'light'
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }

  const applyResolvedTheme = () => {
    if (typeof document === 'undefined') return

    const html = document.documentElement
    html.classList.remove('theme-light', 'theme-dark')
    html.classList.add(resolvedTheme.value === 'dark' ? 'theme-dark' : 'theme-light')
    html.setAttribute('data-theme', resolvedTheme.value)
  }

  const resolveTheme = () => {
    resolvedTheme.value = selectedTheme.value === 'system' ? getSystemTheme() : selectedTheme.value
    applyResolvedTheme()
  }

  const onSystemThemeChanged = () => {
    if (selectedTheme.value !== 'system') return
    resolveTheme()
  }

  const setTheme = (mode: ThemeMode) => {
    selectedTheme.value = mode

    if (typeof window !== 'undefined') {
      window.localStorage.setItem(THEME_STORAGE_KEY, mode)
    }

    resolveTheme()
  }

  const initializeTheme = () => {
    if (typeof window !== 'undefined') {
      const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
      if (saved === 'light' || saved === 'dark' || saved === 'system') {
        selectedTheme.value = saved
      } else {
        selectedTheme.value = 'system'
      }

      mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      mediaQuery.removeEventListener('change', onSystemThemeChanged)
      mediaQuery.addEventListener('change', onSystemThemeChanged)
    }

    resolveTheme()
  }

  return {
    isLoading,
    error,
    thinkingText,
    selectedTheme,
    resolvedTheme,
    setLoading,
    setError,
    clearError,
    setThinking,
    clearThinking,
    setTheme,
    initializeTheme,
    applyResolvedTheme
  }
})
