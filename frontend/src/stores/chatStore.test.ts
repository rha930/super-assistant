import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useChatStore } from '../stores/chatStore'

describe('chatStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('initializes with empty messages', () => {
    const store = useChatStore()
    expect(store.messages).toEqual([])
  })

  it('initializes with an empty user id', () => {
    const store = useChatStore()
    expect(store.userId).toBe('')
  })

  it('adds a message', () => {
    const store = useChatStore()
    store.addMessage({
      id: 'msg_1',
      role: 'user',
      content: 'hello',
      timestamp: new Date(),
      metadata: {}
    })
    expect(store.messages).toHaveLength(1)
    expect(store.messages[0].content).toBe('hello')
  })

  it('updates a message by id', () => {
    const store = useChatStore()
    store.addMessage({
      id: 'msg_1',
      role: 'user',
      content: 'original',
      timestamp: new Date(),
      metadata: {}
    })
    store.updateMessage('msg_1', { content: 'updated' })
    expect(store.messages[0].content).toBe('updated')
  })

  it('clears messages', () => {
    const store = useChatStore()
    store.addMessage({
      id: 'msg_1',
      role: 'user',
      content: 'hello',
      timestamp: new Date(),
      metadata: {}
    })
    store.clearMessages()
    expect(store.messages).toHaveLength(0)
  })

  it('returns empty graphs when no conversation id set', () => {
    const store = useChatStore()
    expect(store.currentGraphs).toEqual([])
  })

  it('setPendingMapAction stores the action', () => {
    const store = useChatStore()
    const action = { action: 'fly_to' as const, lat: 51.5, lng: -0.1, zoom: 10, place_name: 'London' }
    store.setPendingMapAction(action)
    expect(store.pendingMapAction).toEqual(action)
  })

  it('clearPendingMapAction resets pendingMapAction to null', () => {
    const store = useChatStore()
    store.setPendingMapAction({ action: 'fly_to', lat: 0, lng: 0, zoom: 5, place_name: 'Test' })
    store.clearPendingMapAction()
    expect(store.pendingMapAction).toBeNull()
  })
})
