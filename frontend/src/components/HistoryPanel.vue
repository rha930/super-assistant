<template>
  <div class="h-full flex flex-col app-surface border-l app-border">
    <div class="px-4 py-3 border-b app-border flex items-center justify-between">
      <h2 class="text-lg font-semibold">Chat History</h2>
      <button
        class="text-sm px-2 py-1 rounded app-surface-muted hover:opacity-80"
        @click="refresh"
        :disabled="isLoadingConversations"
      >
        Refresh
      </button>
    </div>

    <div class="p-3 border-b app-border">
      <button
        class="w-full px-3 py-2 rounded-lg btn-primary text-sm"
        @click="startNewChat"
      >
        New Chat
      </button>
    </div>

    <div class="flex-1 overflow-y-auto">
      <div v-if="isLoadingConversations" class="p-4 text-sm app-text-muted">
        Loading conversations...
      </div>

      <div v-else-if="conversations.length === 0" class="p-4 text-sm app-text-muted">
        No previous conversations found.
      </div>

      <button
        v-for="conversation in conversations"
        :key="conversation.conversation_id"
        class="w-full text-left p-4 border-b app-border hover:app-surface-muted transition-colors"
        :class="conversation.conversation_id === currentConversationId ? 'app-surface-muted' : ''"
        @click="openConversation(conversation.conversation_id)"
      >
        <div class="flex items-start justify-between gap-2">
          <p class="font-medium text-sm truncate">{{ conversation.preview || 'Untitled conversation' }}</p>
          <span class="text-xs app-text-muted whitespace-nowrap">{{ formatTime(conversation.last_message_at) }}</span>
        </div>
        <p class="text-xs app-text-muted mt-1">{{ conversation.message_count }} messages</p>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useChatStore } from '../stores/chatStore'

const chatStore = useChatStore()

const conversations = computed(() => chatStore.conversations)
const isLoadingConversations = computed(() => chatStore.isLoadingConversations)
const currentConversationId = computed(() => chatStore.currentConversationId)

const refresh = async () => {
  await chatStore.loadConversations()
}

const openConversation = async (conversationId: string) => {
  await chatStore.loadHistory(conversationId)
}

const startNewChat = () => {
  chatStore.clearMessages()
  chatStore.currentConversationId = ''
}

const formatTime = (iso?: string) => {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
}

onMounted(async () => {
  await chatStore.loadConversations()
})
</script>
