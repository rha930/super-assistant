import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './style.css'
import { useUIStore } from './stores/uiStore'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)

const uiStore = useUIStore(pinia)
uiStore.initializeTheme()

app.mount('#app')
