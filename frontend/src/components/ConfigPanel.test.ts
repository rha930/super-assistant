import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../services/api', () => ({
  api: { get: vi.fn(), post: vi.fn() }
}))

import ConfigPanel from './ConfigPanel.vue'
import { api } from '../services/api'

function mockApi(connectors: any[]) {
  ;(api.get as any).mockImplementation((url: string) => {
    if (url === '/api/database/connectors') {
      return Promise.resolve({ data: { data: { connectors } } })
    }
    if (url === '/api/config') {
      return Promise.resolve({ data: { data: {} } })
    }
    if (url === '/api/gemini/models') {
      return Promise.resolve({ data: { data: { models: [], available: false } } })
    }
    // /api/models
    return Promise.resolve({ data: { data: { models: [] } } })
  })
}

describe('ConfigPanel.vue — Database Connectors', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders configured connectors with name, type and status badges', async () => {
    mockApi([
      { name: 'analytics', type: 'postgresql', status: 'connected' },
      { name: 'legacy', type: 'mysql', status: 'unreachable' }
    ])
    const wrapper = mount(ConfigPanel, { global: { plugins: [createPinia()] } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Database Connectors')
    expect(text).toContain('analytics')
    expect(text).toContain('postgresql')
    expect(text).toContain('Connected')
    expect(text).toContain('legacy')
    expect(text).toContain('Unavailable')
  })

  it('shows the empty state when no connectors are configured', async () => {
    mockApi([])
    const wrapper = mount(ConfigPanel, { global: { plugins: [createPinia()] } })
    await flushPromises()

    expect(wrapper.text()).toContain('No database connectors configured.')
  })
})
