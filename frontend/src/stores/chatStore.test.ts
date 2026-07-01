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
})
