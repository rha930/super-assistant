import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

// Provide window.L (CDN global) before the component is imported.
const mockMapInstance = {
  setView: vi.fn().mockReturnThis(),
  on: vi.fn().mockReturnThis(),
  remove: vi.fn(),
  invalidateSize: vi.fn(),
  getCenter: vi.fn().mockReturnValue({ lat: 20, lng: 0 }),
  getZoom: vi.fn().mockReturnValue(2),
}
const mockL = {
  map: vi.fn().mockReturnValue(mockMapInstance),
  tileLayer: vi.fn().mockReturnValue({ addTo: vi.fn() }),
}
;(globalThis as any).L = mockL

// jsdom doesn't implement ResizeObserver
;(globalThis as any).ResizeObserver = class {
  observe() {}
  disconnect() {}
}

import MapPanel from '../components/MapPanel.vue'

describe('MapPanel.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockL.map.mockReturnValue(mockMapInstance)
    mockL.tileLayer.mockReturnValue({ addTo: vi.fn() })
  })

  it('renders the map container element', () => {
    const wrapper = mount(MapPanel, { global: { plugins: [createPinia()] } })
    expect(wrapper.find('[data-testid="map-container"]').exists()).toBe(true)
  })

  it('initializes a Leaflet map on mount', async () => {
    mount(MapPanel, { global: { plugins: [createPinia()] } })
    await flushPromises()
    expect(mockL.map).toHaveBeenCalled()
  })

  it('calls map.remove() on unmount', async () => {
    const wrapper = mount(MapPanel, { global: { plugins: [createPinia()] } })
    await flushPromises()
    wrapper.unmount()
    expect(mockMapInstance.remove).toHaveBeenCalled()
  })

  it('shows a Reset view button', () => {
    const wrapper = mount(MapPanel, { global: { plugins: [createPinia()] } })
    expect(wrapper.text()).toContain('Reset view')
  })

  it('shows the panel title', () => {
    const wrapper = mount(MapPanel, { global: { plugins: [createPinia()] } })
    expect(wrapper.text()).toContain('Map')
  })
})

