import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import NavBar from '../components/NavBar.vue'
import { useNavStore } from '../stores/navStore'

vi.mock('../stores/notesStore', () => ({
  useNotesStore: () => ({ exitNoteTakingMode: vi.fn() }),
}))

describe('NavBar.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders three nav buttons', () => {
    const wrapper = mount(NavBar, { global: { plugins: [createPinia()] } })
    expect(wrapper.findAll('button')).toHaveLength(3)
  })

  it('renders correct aria-labels', () => {
    const wrapper = mount(NavBar, { global: { plugins: [createPinia()] } })
    const labels = wrapper.findAll('button').map(b => b.attributes('aria-label'))
    expect(labels).toContain('Toggle graphs')
    expect(labels).toContain('Notes')
    expect(labels).toContain('Map')
  })

  it('clicking a button updates navStore activeModule', async () => {
    const wrapper = mount(NavBar, { global: { plugins: [createPinia()] } })
    const store = useNavStore()
    expect(store.activeModule).toBeNull()

    const graphBtn = wrapper.findAll('button').find(b => b.attributes('aria-label') === 'Toggle graphs')!
    await graphBtn.trigger('click')
    expect(store.activeModule).toBe('graph')
  })

  it('active button has aria-pressed="true"', async () => {
    const wrapper = mount(NavBar, { global: { plugins: [createPinia()] } })
    const store = useNavStore()
    store.selectModule('map')
    await wrapper.vm.$nextTick()

    const mapBtn = wrapper.findAll('button').find(b => b.attributes('aria-label') === 'Map')!
    expect(mapBtn.attributes('aria-pressed')).toBe('true')
  })

  it('inactive buttons have aria-pressed="false"', async () => {
    const wrapper = mount(NavBar, { global: { plugins: [createPinia()] } })
    const store = useNavStore()
    store.selectModule('notes')
    await wrapper.vm.$nextTick()

    const graphBtn = wrapper.findAll('button').find(b => b.attributes('aria-label') === 'Toggle graphs')!
    expect(graphBtn.attributes('aria-pressed')).toBe('false')
  })
})
