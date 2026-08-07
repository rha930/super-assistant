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

  describe('coordinate points', () => {
    it('starts with empty points and counter at 0', () => {
      const store = useMapStore()
      expect(store.points).toEqual([])
      expect(store.pointCounter).toBe(0)
    })

    it('addPoint appends a point with correct lat/lng and auto-label', () => {
      const store = useMapStore()
      const p = store.addPoint(48.8, 2.3)
      expect(store.points).toHaveLength(1)
      expect(p.lat).toBe(48.8)
      expect(p.lng).toBe(2.3)
      expect(p.label).toBe('Point 1')
    })

    it('addPoint increments label counter across multiple calls', () => {
      const store = useMapStore()
      store.addPoint(0, 0)
      const p = store.addPoint(1, 1)
      expect(p.label).toBe('Point 2')
      expect(store.points).toHaveLength(2)
    })

    it('removePoint removes the correct point and leaves others', () => {
      const store = useMapStore()
      const a = store.addPoint(10, 10)
      const b = store.addPoint(20, 20)
      store.removePoint(a.id)
      expect(store.points).toHaveLength(1)
      expect(store.points[0].id).toBe(b.id)
    })

    it('updatePointLabel updates only the named point label', () => {
      const store = useMapStore()
      const a = store.addPoint(10, 10)
      const b = store.addPoint(20, 20)
      store.updatePointLabel(a.id, 'My Place')
      expect(store.points.find((p) => p.id === a.id)?.label).toBe('My Place')
      expect(store.points.find((p) => p.id === b.id)?.label).toBe('Point 2')
    })
  })
})
