import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Message } from '../types/message'
import type { GraphPayload } from '../types/graph'
import { api } from '../services/api'
import { extractGraphArtifacts } from '../services/graphValidator'
import { useUIStore } from './uiStore'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const currentConversationId = ref<string>('')
  const graphsByConversationId = ref<Map<string, GraphPayload[]>>(new Map())
  const selectedGraphIdByConversationId = ref<Map<string, string>>(new Map())
  const uiStore = useUIStore()

  const addMessage = (message: Message) => {
    messages.value.push(message)
  }

  const updateMessage = (id: string, partial: Partial<Message>) => {
    const idx = messages.value.findIndex((m) => m.id === id)
    if (idx >= 0) {
      messages.value[idx] = {
        ...messages.value[idx],
        ...partial
      }
    }
  }

  const currentGraphs = computed(() => {
    return graphsByConversationId.value.get(currentConversationId.value) || []
  })

  const selectedGraphId = computed(() => {
    return selectedGraphIdByConversationId.value.get(currentConversationId.value)
  })

  const selectedGraph = computed(() => {
    if (!selectedGraphId.value) return null
    return currentGraphs.value.find((g) => g.id === selectedGraphId.value) || null
  })

  const addGraphs = (graphs: GraphPayload[]) => {
    if (graphs.length === 0) return
    const existing = graphsByConversationId.value.get(currentConversationId.value) || []
    const merged = [...existing]

    for (const graph of graphs) {
      const alreadyExists = merged.some((g) => g.id === graph.id)
      if (!alreadyExists) {
        merged.push(graph)
      }
    }

    graphsByConversationId.value.set(currentConversationId.value, merged)
    if (merged.length > 0 && !selectedGraphId.value) {
      selectedGraphIdByConversationId.value.set(currentConversationId.value, merged[0].id)
    }
  }

  const selectGraph = (graphId: string) => {
    if (currentGraphs.value.some((g) => g.id === graphId)) {
      selectedGraphIdByConversationId.value.set(currentConversationId.value, graphId)
    }
  }

  const sendMessage = async (content: string) => {
    // Add user message
    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
      metadata: {}
    }
    addMessage(userMessage)

    uiStore.setLoading(true)
    uiStore.clearError()
    uiStore.setThinking('Reviewing your request...')

    const agentMessageId = `msg_${Date.now()}_agent`
    const streamingMessage: Message = {
      id: agentMessageId,
      role: 'agent',
      content: '',
      timestamp: new Date(),
      metadata: {}
    }
    addMessage(streamingMessage)

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000'
      const response = await fetch(`${apiUrl}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          message: content,
          conversation_id: currentConversationId.value
        })
      })

      if (!response.ok) {
        throw new Error(`Stream request failed: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('No stream body returned by backend')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const event of events) {
          const line = event
            .split('\n')
            .find((l) => l.startsWith('data: '))
          if (!line) continue

          const payload = JSON.parse(line.slice(6))

          if (payload.error) {
            throw new Error(payload.error)
          }

          if (payload.thinking) {
            uiStore.setThinking(payload.thinking)
          }

          if (payload.conversation_id) {
            currentConversationId.value = payload.conversation_id
          }

          if (payload.chunk) {
            const existing = messages.value.find((m) => m.id === agentMessageId)
            const nextContent = `${existing?.content || ''}${payload.chunk}`
            updateMessage(agentMessageId, { content: nextContent })
          }

          if (payload.done) {
            updateMessage(agentMessageId, { metadata: payload.metadata || {} })
            // Extract and add graphs from message artifacts
            const artifactSource = payload.artifacts || payload.metadata?.artifacts
            if (artifactSource) {
              const graphs = extractGraphArtifacts(artifactSource)
              if (graphs.length > 0) {
                addGraphs(graphs)
              }
            }
            uiStore.clearThinking()
          }
        }
      }

      const finalMsg = messages.value.find((m) => m.id === agentMessageId)
      if (!finalMsg || !finalMsg.content.trim()) {
        updateMessage(agentMessageId, { content: '[No response received]' })
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      updateMessage(agentMessageId, { content: '[Error: failed to stream response]' })
      uiStore.setError('Failed to stream message')
      uiStore.clearThinking()
    } finally {
      uiStore.setLoading(false)
      uiStore.clearThinking()
    }
  }

  const clearMessages = () => {
    messages.value = []
  }

  const loadHistory = async (conversationId: string) => {
    try {
      const response = await api.get(`/api/chat/history/${conversationId}`)
      messages.value = response.data?.data?.messages || []
      currentConversationId.value = conversationId
    } catch (error) {
      console.error('Failed to load history:', error)
    }
  }

  return {
    messages,
    currentConversationId,
    currentGraphs,
    selectedGraphId,
    selectedGraph,
    addMessage,
    updateMessage,
    sendMessage,
    clearMessages,
    loadHistory,
    addGraphs,
    selectGraph
  }
})
