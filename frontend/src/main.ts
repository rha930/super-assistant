import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'

// Inject Leaflet CSS + JS from CDN so the Map panel works without npm leaflet in node_modules
const _win = window as any
if (!_win.L) {
  const css = document.createElement('link')
  css.rel = 'stylesheet'
  css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
  document.head.appendChild(css)

  const js = document.createElement('script')
  js.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
  document.head.appendChild(js)
}
import { useUIStore } from './stores/uiStore'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const uiStore = useUIStore(pinia)
uiStore.initializeTheme()

app.mount('#app')
