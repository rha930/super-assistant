<template>
  <div class="flex flex-col h-full">
    <!-- Messages Container -->
    <div class="flex-1 overflow-y-auto p-6 space-y-4" ref="messagesContainer">
      <div
        v-if="messages.length === 0"
        class="flex items-center justify-center h-full app-text-muted"
      >
        <p class="text-center">
          <span class="text-3xl mb-2 block">💬</span>
          No messages yet. Start a conversation!
        </p>
      </div>
      <Message
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />
      <div v-if="isLoading" class="flex justify-start">
        <div class="app-surface-muted rounded-lg px-4 py-2 flex items-center gap-2 app-text">
          <span class="flex-shrink-0 w-5 h-5 rounded-full bg-green-600 text-white text-[10px] font-semibold flex items-center justify-center">
            A
          </span>
          <span class="animate-pulse">{{ thinkingText }}</span>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="border-t app-border app-surface p-6">
      <form @submit.prevent="sendMessage" class="flex gap-3">
        <input
          v-model="inputValue"
          :disabled="isLoading"
          type="text"
          placeholder="Type your message..."
          class="flex-1 px-4 py-2 border app-border rounded-lg focus:outline-none focus:ring-2 disabled:opacity-60 app-surface app-text"
          style="--tw-ring-color: var(--color-accent);"
        />
        <button
          type="submit"
          :disabled="isLoading || !inputValue.trim()"
          class="px-6 py-2 btn-primary rounded-lg disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUpdated } from 'vue'
import { useChatStore } from '../stores/chatStore'
import { useUIStore } from '../stores/uiStore'
import Message from './Message.vue'

const chatStore = useChatStore()
const uiStore = useUIStore()
const messagesContainer = ref<HTMLElement>()
const inputValue = ref('')

const messages = computed(() => chatStore.messages)
const isLoading = computed(() => uiStore.isLoading)
const thinkingText = computed(() => uiStore.thinkingText || 'Agent is thinking...')

const sendMessage = async () => {
  if (!inputValue.value.trim()) return

  const message = inputValue.value
  inputValue.value = ''
  
  await chatStore.sendMessage(message)
}

// Auto-scroll to bottom when new messages arrive
onUpdated(() => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
})
</script>
