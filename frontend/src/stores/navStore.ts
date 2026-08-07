import { defineStore } from 'pinia'
import { ref } from 'vue'

export type NavModule = 'graph' | 'notes' | 'map'

export const useNavStore = defineStore('nav', () => {
  const activeModule = ref<NavModule | null>(null)

  function selectModule(module: NavModule) {
    const closing = activeModule.value === module

    // Always exit note-taking mode when leaving Notes (close or switch)
    if (activeModule.value === 'notes' || (closing && module === 'notes')) {
      // Lazy import to avoid circular dependency at module init time
      import('./notesStore').then(({ useNotesStore }) => {
        useNotesStore().exitNoteTakingMode()
      })
    }

    activeModule.value = closing ? null : module
  }

  return { activeModule, selectModule }
})
