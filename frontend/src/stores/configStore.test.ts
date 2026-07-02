import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('../services/api', () => ({
  api: { get: vi.fn(), post: vi.fn() }
}))

import { useConfigStore } from '../stores/configStore'
import { api } from '../services/api'

describe('configStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('defaults provider to ollama', () => {
    const store = useConfigStore()
    expect(store.config.provider).toBe('ollama')
  })

  it('activeModels returns ollama models when provider is ollama', () => {
    const store = useConfigStore()
    store.availableModels = ['llama3', 'mistral']
    store.geminiModels = ['gemini-1.5-flash']
    store.config.provider = 'ollama'
    expect(store.activeModels).toEqual(['llama3', 'mistral'])
  })

  it('activeModels returns gemini models when provider is gemini', () => {
    const store = useConfigStore()
    store.availableModels = ['llama3', 'mistral']
    store.geminiModels = ['gemini-1.5-flash', 'gemini-1.5-pro']
    store.config.provider = 'gemini'
    expect(store.activeModels).toEqual(['gemini-1.5-flash', 'gemini-1.5-pro'])
  })

  it('loadGeminiModels sets models and availability', async () => {
    ;(api.get as any).mockResolvedValue({
      data: { data: { models: ['gemini-1.5-flash'], available: true } }
    })
    const store = useConfigStore()
    await store.loadGeminiModels()
    expect(store.geminiModels).toEqual(['gemini-1.5-flash'])
    expect(store.geminiAvailable).toBe(true)
  })

  it('loadGeminiModels handles failure gracefully', async () => {
    ;(api.get as any).mockRejectedValue(new Error('network'))
    const store = useConfigStore()
    await store.loadGeminiModels()
    expect(store.geminiModels).toEqual([])
    expect(store.geminiAvailable).toBe(false)
  })
})
