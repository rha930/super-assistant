import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

// Provide window.L (CDN global) before the component is imported.
const mockMarkerInstance = {
  addTo: vi.fn().mockReturnThis(),
  bindTooltip: vi.fn().mockReturnThis(),
  bindPopup: vi.fn().mockReturnThis(),
  openPopup: vi.fn().mockReturnThis(),
  closePopup: vi.fn().mockReturnThis(),
  on: vi.fn().mockReturnThis(),
  remove: vi.fn(),
  setTooltipContent: vi.fn(),
}
const mockMapInstance = {
  setView: vi.fn().mockReturnThis(),
  flyTo: vi.fn().mockReturnThis(),
  on: vi.fn().mockReturnThis(),
  remove: vi.fn(),
  invalidateSize: vi.fn(),
  closePopup: vi.fn(),
  getCenter: vi.fn().mockReturnValue({ lat: 20, lng: 0 }),
  getZoom: vi.fn().mockReturnValue(2),
}
const mockL = {
  map: vi.fn().mockReturnValue(mockMapInstance),
  tileLayer: vi.fn().mockReturnValue({ addTo: vi.fn() }),
  marker: vi.fn().mockReturnValue(mockMarkerInstance),
  popup: vi.fn().mockReturnValue({
    setLatLng: vi.fn().mockReturnThis(),
    setContent: vi.fn().mockReturnThis(),
    openOn: vi.fn().mockReturnThis(),
  }),
  DomEvent: { stopPropagation: vi.fn() },
}
;(globalThis as any).L = mockL

// jsdom doesn't implement ResizeObserver
;(globalThis as any).ResizeObserver = class {
  observe() {}
  disconnect() {}
}

import MapPanel from './MapPanel.vue'
import { useMapStore } from '../stores/mapStore'
import { useChatStore } from '../stores/chatStore'

describe('MapPanel.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockL.map.mockReturnValue(mockMapInstance)
    mockL.tileLayer.mockReturnValue({ addTo: vi.fn() })
    mockL.marker.mockReturnValue(mockMarkerInstance)
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

  it('restores pre-existing store points on mount via L.marker', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useMapStore()
    store.addPoint(48.8, 2.3)

    mount(MapPanel, { global: { plugins: [pinia] } })
    await flushPromises()

    // L.marker should have been called once for the restored point
    expect(mockL.marker).toHaveBeenCalledTimes(1)
    expect(mockL.marker).toHaveBeenCalledWith([48.8, 2.3])
  })

  it('calls map.flyTo when pendingMapAction is set after mount', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const chatStore = useChatStore()

    mount(MapPanel, { global: { plugins: [pinia] } })
    await flushPromises()

    chatStore.setPendingMapAction({ action: 'fly_to', lat: 51.5, lng: -0.1, zoom: 10, place_name: 'London' })
    await flushPromises()

    expect(mockMapInstance.flyTo).toHaveBeenCalledWith([51.5, -0.1], 10)
    expect(chatStore.pendingMapAction).toBeNull()
  })
})

