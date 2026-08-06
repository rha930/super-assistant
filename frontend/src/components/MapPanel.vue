<template>
  <div class="flex flex-col h-full app-surface border-r app-border">
    <!-- Header -->
    <div class="px-4 py-3 border-b app-border flex items-center justify-between shrink-0">
      <h2 class="text-lg font-semibold app-text">Map</h2>
      <button
        @click="mapStore.toggleMapPanel()"
        class="p-1 app-text-muted hover:opacity-80 transition-opacity"
        aria-label="Close map panel"
        title="Close"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
          <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
        </svg>
      </button>
    </div>

    <!-- Controls row -->
    <div class="px-4 py-2 border-b app-border flex items-center gap-2 shrink-0">
      <button
        @click="resetView"
        class="px-3 py-1 text-xs app-surface-muted app-text-muted rounded hover:opacity-80 transition-opacity"
        title="Reset to world view"
      >
        Reset view
      </button>
    </div>

    <!-- Map container — explicit min-height ensures Leaflet gets a non-zero size -->
    <div ref="mapContainer" class="flex-1 min-h-0" style="min-height: 200px" data-testid="map-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useMapStore } from '../stores/mapStore'

const mapStore = useMapStore()
const mapContainer = ref<HTMLElement | null>(null)
let map: any = null

function resetView() {
  mapStore.resetView()
  map?.setView(mapStore.lastCenter, mapStore.lastZoom)
}

onMounted(async () => {
  await nextTick()
  if (!mapContainer.value) return

  // Wait for the Leaflet CDN script injected by main.ts to finish loading
  const w = window as any
  if (!w.L) {
    await new Promise<void>((resolve) => {
      const interval = setInterval(() => {
        if (w.L) { clearInterval(interval); resolve() }
      }, 50)
      // Give up after 10 s to avoid hanging indefinitely
      setTimeout(() => { clearInterval(interval); resolve() }, 10_000)
    })
  }
  if (!w.L || !mapContainer.value) return

  const L = w.L
  map = L.map(mapContainer.value, {
    center: mapStore.lastCenter,
    zoom: mapStore.lastZoom,
  })

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map)

  map.invalidateSize()

  map.on('moveend zoomend', () => {
    if (!map) return
    const c = map.getCenter()
    mapStore.setView([c.lat, c.lng], map.getZoom())
  })
})

onBeforeUnmount(() => {
  map?.remove()
  map = null
})
</script>
