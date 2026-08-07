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
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import type { MapPoint } from '../stores/mapStore'
import { useMapStore } from '../stores/mapStore'
import { useChatStore } from '../stores/chatStore'
import { useNavStore } from '../stores/navStore'

const mapStore = useMapStore()
const chatStore = useChatStore()
const navStore = useNavStore()
const mapContainer = ref<HTMLElement | null>(null)
let map: any = null
let resizeObserver: ResizeObserver | null = null
// keyed by MapPoint.id for O(1) lookup on delete
const markerLayer = new Map<string, any>()

function resetView() {
  mapStore.resetView()
  map?.setView(mapStore.lastCenter, mapStore.lastZoom)
}

function escAttr(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function placeMarker(L: any, point: MapPoint) {
  const marker = L.marker([point.lat, point.lng])
  marker.bindTooltip(point.label, { permanent: true, direction: 'top', offset: [0, -30] })

  // Left-click: edit label
  marker.on('click', () => {
    const inputId = `edit-input-${point.id}`
    const saveId = `edit-save-${point.id}`
    const current = mapStore.points.find((p) => p.id === point.id)?.label ?? point.label
    marker
      .bindPopup(
        `<div style="min-width:180px;padding:2px">
          <input id="${inputId}" type="text" value="${escAttr(current)}"
            style="width:100%;border:1px solid #ccc;border-radius:4px;padding:4px;box-sizing:border-box;margin-bottom:6px"/>
          <button id="${saveId}"
            style="width:100%;background:#3b82f6;color:#fff;border:none;border-radius:4px;padding:4px 8px;cursor:pointer">
            Save
          </button>
        </div>`,
      )
      .openPopup()
    setTimeout(() => {
      const input = document.getElementById(inputId) as HTMLInputElement | null
      const btn = document.getElementById(saveId)
      input?.select()
      if (input && btn) {
        btn.onclick = () => {
          const newLabel = input.value.trim() || current
          mapStore.updatePointLabel(point.id, newLabel)
          marker.setTooltipContent(newLabel)
          marker.closePopup()
        }
        input.onkeydown = (e) => {
          if (e.key === 'Enter') btn.click()
        }
      }
    }, 50)
  })

  // Right-click on marker: delete (stop propagation so map contextmenu doesn't also fire)
  marker.on('contextmenu', (ev: any) => {
    L.DomEvent.stopPropagation(ev)
    const deleteId = `del-${point.id}`
    marker
      .bindPopup(
        `<button id="${deleteId}"
          style="color:#ef4444;padding:4px 8px;border:1px solid #ef4444;border-radius:4px;cursor:pointer;background:transparent">
          Delete point
        </button>`,
      )
      .openPopup()
    setTimeout(() => {
      const btn = document.getElementById(deleteId)
      if (btn) {
        btn.onclick = () => {
          mapStore.removePoint(point.id)
          markerLayer.get(point.id)?.remove()
          markerLayer.delete(point.id)
        }
      }
    }, 50)
  })

  marker.addTo(map)
  markerLayer.set(point.id, marker)
}

function restorePoints(L: any) {
  mapStore.points.forEach((p) => placeMarker(L, p))
}

onMounted(async () => {
  await nextTick()
  if (!mapContainer.value) return

  // Wait for the Leaflet CDN script injected by main.ts to finish loading
  const w = window as any
  if (!w.L) {
    await new Promise<void>((resolve) => {
      const interval = setInterval(() => {
        if (w.L) {
          clearInterval(interval)
          resolve()
        }
      }, 50)
      // Give up after 10 s to avoid hanging indefinitely
      setTimeout(() => {
        clearInterval(interval)
        resolve()
      }, 10_000)
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

  // Re-render tiles whenever the panel is resized
  resizeObserver = new ResizeObserver(() => map?.invalidateSize())
  resizeObserver.observe(mapContainer.value)

  map.on('moveend zoomend', () => {
    if (!map) return
    const c = map.getCenter()
    mapStore.setView([c.lat, c.lng], map.getZoom())
  })

  // Right-click on empty map canvas: add a point
  map.on('contextmenu', (e: any) => {
    const addId = `add-${Date.now()}`
    L.popup()
      .setLatLng(e.latlng)
      .setContent(
        `<button id="${addId}"
          style="padding:4px 10px;border:1px solid #3b82f6;color:#3b82f6;border-radius:4px;cursor:pointer;background:transparent">
          Add point here
        </button>`,
      )
      .openOn(map)
    setTimeout(() => {
      const btn = document.getElementById(addId)
      if (btn) {
        btn.onclick = () => {
          const point = mapStore.addPoint(e.latlng.lat, e.latlng.lng)
          placeMarker(L, point)
          map.closePopup()
        }
      }
    }, 50)
  })

  // Restore any markers placed in a previous panel open this session
  restorePoints(L)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  markerLayer.clear()
  map?.remove()
  map = null
})

// Fly to location when the agent emits a map_action artifact
watch(
  () => chatStore.pendingMapAction,
  (action) => {
    if (!action || action.action !== 'fly_to') return
    if (navStore.activeModule !== 'map') {
      navStore.selectModule('map')
    }
    nextTick(() => {
      map?.flyTo([action.lat, action.lng], action.zoom)
      mapStore.setView([action.lat, action.lng], action.zoom)
      chatStore.clearPendingMapAction()
    })
  },
)
</script>
