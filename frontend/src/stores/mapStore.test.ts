import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMapStore } from '../stores/mapStore'

describe('mapStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('default state', () => {
    it('panel is hidden by default', () => {
      const store = useMapStore()
      expect(store.showMapPanel).toBe(false)
    })

    it('defaults to center [20, 0] and zoom 2', () => {
      const store = useMapStore()
      expect(store.lastCenter).toEqual([20, 0])
      expect(store.lastZoom).toBe(2)
    })
  })

  describe('toggleMapPanel', () => {
    it('opens the panel when closed', () => {
      const store = useMapStore()
      store.toggleMapPanel()
      expect(store.showMapPanel).toBe(true)
    })

    it('closes the panel when open', () => {
      const store = useMapStore()
      store.toggleMapPanel()
      store.toggleMapPanel()
      expect(store.showMapPanel).toBe(false)
    })
  })

  describe('setView', () => {
    it('updates lastCenter and lastZoom', () => {
      const store = useMapStore()
      store.setView([51.5, -0.1], 10)
      expect(store.lastCenter).toEqual([51.5, -0.1])
      expect(store.lastZoom).toBe(10)
    })

    it('persists last set values', () => {
      const store = useMapStore()
      store.setView([35.7, 139.7], 8)
      store.setView([48.9, 2.3], 12)
      expect(store.lastCenter).toEqual([48.9, 2.3])
      expect(store.lastZoom).toBe(12)
    })
  })

  describe('resetView', () => {
    it('restores default center and zoom after navigation', () => {
      const store = useMapStore()
      store.setView([51.5, -0.1], 10)
      store.resetView()
      expect(store.lastCenter).toEqual([20, 0])
      expect(store.lastZoom).toBe(2)
    })
  })
})
