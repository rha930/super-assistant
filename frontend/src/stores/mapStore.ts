import { defineStore } from 'pinia'
import { ref } from 'vue'

const DEFAULT_CENTER: [number, number] = [20, 0]
const DEFAULT_ZOOM = 2

export const useMapStore = defineStore('map', () => {
  const showMapPanel = ref(false)
  const lastCenter = ref<[number, number]>([...DEFAULT_CENTER])
  const lastZoom = ref(DEFAULT_ZOOM)

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

  return { showMapPanel, lastCenter, lastZoom, toggleMapPanel, setView, resetView }
})
