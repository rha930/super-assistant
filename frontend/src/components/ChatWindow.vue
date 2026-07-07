<template>
  <div class="flex flex-col h-full">
    <!-- Messages Container -->
    <div class="flex-1 overflow-y-auto p-6 space-y-4" ref="messagesContainer">
      <div
        v-if="messages.length === 0 && !noteTakingMode"
        class="flex items-center justify-center h-full app-text-muted"
      >
        <p class="text-center">
          <span class="text-3xl mb-2 block">💬</span>
          No messages yet. Start a conversation!
        </p>
      </div>
      <div
        v-else-if="messages.length === 0 && noteTakingMode"
        class="flex items-center justify-center h-full app-text-muted"
      >
        <p class="text-center">
          <span class="text-3xl mb-2 block">📝</span>
          Note-taking mode active. Type to add to your note.
        </p>
      </div>
      <Message
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- Note suggestion card -->
      <div v-if="pendingSuggestion" class="flex items-start gap-3">
        <div class="flex-shrink-0 w-8 h-8 rounded-full bg-green-600 text-white text-sm font-semibold flex items-center justify-center">
          A
        </div>
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-semibold text-sm app-text">Agent</span>
            <span class="text-xs px-1.5 py-0.5 bg-green-600 text-white rounded-full">Note suggestion</span>
          </div>
          <div class="border app-border rounded-lg p-4 app-surface-muted">
            <div class="markdown-content app-text text-sm" v-html="renderedSuggestion"></div>
            <div class="mt-3 flex gap-2">
              <button
                @click="handleAccept"
                class="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                Accept (a)
              </button>
              <button
                @click="handleDeny"
                class="px-3 py-1.5 text-sm bg-red-500 text-white rounded-md hover:bg-red-600 transition-colors"
              >
                Deny (d)
              </button>
              <button
                @click="handleExpandMore"
                :disabled="notesStore.expandCount >= notesStore.maxExpansions"
                class="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Expand more (e)
              </button>
            </div>
            <div v-if="notesStore.expandCount >= notesStore.maxExpansions" class="mt-2 text-xs app-text-muted">
              Maximum expansions reached. Accept or deny to continue.
            </div>
          </div>
        </div>
      </div>

      <div v-if="isLoading || isExpanding" class="flex justify-start">
        <div class="app-surface-muted rounded-lg px-4 py-2 flex items-center gap-2 app-text">
          <span class="flex-shrink-0 w-5 h-5 rounded-full bg-green-600 text-white text-[10px] font-semibold flex items-center justify-center">
            A
          </span>
          <span class="animate-pulse">{{ isExpanding ? 'Expanding note...' : thinkingText }}</span>
        </div>
      </div>
    </div>

    <!-- Note-taking mode indicator -->
    <div v-if="noteTakingMode" class="border-t border-green-500 bg-green-50 dark:bg-green-900/20 px-6 py-2 flex items-center justify-between">
      <span class="text-sm text-green-700 dark:text-green-300">
        📝 Note-taking mode — {{ notesStore.activeNote?.title || 'Untitled' }}
      </span>
      <button
        @click="notesStore.exitNoteTakingMode()"
        class="text-xs text-green-600 dark:text-green-400 hover:underline"
      >
        Exit
      </button>
    </div>

    <!-- Input Area -->
    <div class="border-t app-border app-surface p-6">
      <form @submit.prevent="sendMessage" class="flex gap-3">
        <input
          v-model="inputValue"
          :disabled="isLoading || isExpanding"
          type="text"
          :placeholder="noteTakingMode ? 'Type note content...' : 'Type your message...'"
          class="flex-1 px-4 py-2 border app-border rounded-lg focus:outline-none focus:ring-2 disabled:opacity-60 app-surface app-text"
          :style="noteTakingMode ? 'border-left: 3px solid #16a34a; --tw-ring-color: #16a34a;' : '--tw-ring-color: var(--color-accent);'"
        />
        <button
          type="submit"
          :disabled="isLoading || isExpanding || !inputValue.trim()"
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
import { useNotesStore } from '../stores/notesStore'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import Message from './Message.vue'

const chatStore = useChatStore()
const uiStore = useUIStore()
const notesStore = useNotesStore()
const messagesContainer = ref<HTMLElement>()
const inputValue = ref('')

const messages = computed(() => chatStore.messages)
const isLoading = computed(() => uiStore.isLoading)
const thinkingText = computed(() => uiStore.thinkingText || 'Agent is thinking...')
const noteTakingMode = computed(() => notesStore.noteTakingMode)
const pendingSuggestion = computed(() => notesStore.pendingSuggestion)
const isExpanding = computed(() => notesStore.isExpanding)

marked.setOptions({ breaks: true, gfm: true })

const renderedSuggestion = computed(() => {
  if (!pendingSuggestion.value) return ''
  const html = marked.parse(pendingSuggestion.value.suggestion) as string
  return DOMPurify.sanitize(html)
})

const sendMessage = async () => {
  if (!inputValue.value.trim()) return
  const message = inputValue.value
  inputValue.value = ''

  // Check for shortcut keys when a suggestion is pending
  const shortcut = notesStore.getShortcutAction(message)
  if (shortcut) {
    if (shortcut === 'accept') await handleAccept()
    else if (shortcut === 'deny') await handleDeny()
    else if (shortcut === 'expand') await handleExpandMore()
    return
  }

  // Block new messages while a suggestion is pending
  if (pendingSuggestion.value) {
    return
  }

  // Note-taking mode: expand input via LLM
  if (noteTakingMode.value) {
    // Show user message in chat
    chatStore.addMessage({
      id: `msg_${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date(),
      metadata: {},
    })
    try {
      await notesStore.expandInput(message)
    } catch {
      // LLM expansion failed — fall back to deny (append raw text)
      if (notesStore.activeNote) {
        await notesStore.denySuggestion()
        chatStore.addMessage({
          id: `msg_${Date.now()}_err`,
          role: 'agent',
          content: 'Could not expand note. Your original text has been added.',
          timestamp: new Date(),
          metadata: {},
        })
      }
    }
    return
  }

  // Normal chat
  await chatStore.sendMessage(message)
}

async function handleAccept() {
  const result = await notesStore.acceptSuggestion()
  if (result) {
    chatStore.addMessage({
      id: `msg_${Date.now()}_confirm`,
      role: 'agent',
      content: `✅ ${result}`,
      timestamp: new Date(),
      metadata: {},
    })
  }
}

async function handleDeny() {
  const result = await notesStore.denySuggestion()
  if (result) {
    chatStore.addMessage({
      id: `msg_${Date.now()}_confirm`,
      role: 'agent',
      content: `📝 ${result}`,
      timestamp: new Date(),
      metadata: {},
    })
  }
}

async function handleExpandMore() {
  if (notesStore.expandCount >= notesStore.maxExpansions) return
  await notesStore.expandMore()
}

// Auto-scroll to bottom when new messages arrive
onUpdated(() => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
})
</script>

<style scoped>
.markdown-content :deep(p) { margin: 0.25rem 0; }
.markdown-content :deep(ul),
.markdown-content :deep(ol) { padding-left: 1.25rem; margin: 0.25rem 0; }
.markdown-content :deep(code) {
  background: var(--color-surface-muted);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
}
.markdown-content :deep(pre) {
  background: var(--color-surface-muted);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 0.4rem 0;
}
.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
}
</style>
