import { defineStore } from 'pinia'
import { ref } from 'vue'

const DEFAULT_CENTER: [number, number] = [20, 0]
const DEFAULT_ZOOM = 2

export interface MapPoint {
  id: string
  lat: number
  lng: number
  label: string
}

export const useMapStore = defineStore('map', () => {
  const showMapPanel = ref(false)
  const lastCenter = ref<[number, number]>([...DEFAULT_CENTER])
  const lastZoom = ref(DEFAULT_ZOOM)

  // Session-persistent coordinate points
  const points = ref<MapPoint[]>([])
  const pointCounter = ref(0)

  function toggleMapPanel() {
    showMapPanel.value = !showMapPanel.value
  }

  function setView(center: [number, number], zoom: number) {
    lastCenter.value = center
    lastZoom.value = zoom
  }

  function resetView() {
    lastCenter.value = [...DEFAULT_CENTER]
    lastZoom.value = DEFAULT_ZOOM
  }

  function addPoint(lat: number, lng: number): MapPoint {
    pointCounter.value += 1
    const point: MapPoint = {
      id: crypto.randomUUID(),
      lat,
      lng,
      label: `Point ${pointCounter.value}`,
    }
    points.value = [...points.value, point]
    return point
  }

  function removePoint(id: string) {
    points.value = points.value.filter((p) => p.id !== id)
  }

  function updatePointLabel(id: string, label: string) {
    points.value = points.value.map((p) => (p.id === id ? { ...p, label } : p))
  }

  function updatePointCoords(id: string, lat: number, lng: number) {
    points.value = points.value.map((p) => (p.id === id ? { ...p, lat, lng } : p))
  }

  return {
    showMapPanel,
    lastCenter,
    lastZoom,
    points,
    pointCounter,
    toggleMapPanel,
    setView,
    resetView,
    addPoint,
    removePoint,
    updatePointLabel,
    updatePointCoords,
  }
})
