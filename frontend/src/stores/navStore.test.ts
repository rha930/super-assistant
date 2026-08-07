import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useNavStore } from '../stores/navStore'

vi.mock('../stores/notesStore', () => ({
  useNotesStore: () => ({ exitNoteTakingMode: vi.fn() }),
}))

describe('navStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('defaults to null activeModule', () => {
    expect(useNavStore().activeModule).toBeNull()
  })

  it('selectModule sets activeModule', () => {
    const store = useNavStore()
    store.selectModule('graph')
    expect(store.activeModule).toBe('graph')
  })

  it('selectModule same module toggles to null', () => {
    const store = useNavStore()
    store.selectModule('graph')
    store.selectModule('graph')
    expect(store.activeModule).toBeNull()
  })

  it('selectModule different module switches directly', () => {
    const store = useNavStore()
    store.selectModule('graph')
    store.selectModule('notes')
    expect(store.activeModule).toBe('notes')
  })

  it('selectModule each module sets it correctly', () => {
    const store = useNavStore()
    for (const m of ['graph', 'notes', 'map'] as const) {
      store.selectModule(m)
      expect(store.activeModule).toBe(m)
    }
  })
})
