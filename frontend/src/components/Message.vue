<template>
  <div class="flex items-start gap-3">
    <!-- Avatar -->
    <div
      :class="[
        'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-semibold',
        message.role === 'user' ? 'bg-blue-600' : 'bg-green-600'
      ]"
    >
      {{ message.role === 'user' ? 'U' : 'A' }}
    </div>

    <!-- Message Content -->
    <div class="flex-1">
      <div class="flex items-center gap-2">
        <span class="font-semibold text-sm app-text">
          {{ message.role === 'user' ? 'You' : 'Agent' }}
        </span>
        <span class="text-xs app-text-muted">
          {{ formatTime(message.timestamp) }}
        </span>
      </div>
      <div
        class="app-text mt-1 break-words markdown-content"
        v-html="renderedContent"
      ></div>
      <div v-if="message.metadata?.tool_calls && message.metadata.tool_calls.length > 0" class="mt-2 text-xs app-text-muted">
        <span class="font-semibold">Tool calls:</span> {{ message.metadata.tool_calls.length }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Message as MessageType } from '../types/message'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

interface Props {
  message: MessageType
}

const props = defineProps<Props>()

marked.setOptions({
  breaks: true,
  gfm: true
})

const renderedContent = computed(() => {
  const raw = props.message.content || ''
  const html = marked.parse(raw)
  return DOMPurify.sanitize(html)
})

const formatTime = (timestamp: Date) => {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.markdown-content :deep(p) {
  margin: 0.25rem 0;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 1.25rem;
  margin: 0.25rem 0;
}

.markdown-content :deep(code) {
  background: var(--color-surface-muted);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
  font-size: 0.85em;
}

.markdown-content :deep(pre) {
  background: var(--color-surface-muted);
  color: var(--color-text);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin: 0.4rem 0;
  border: 1px solid var(--color-border);
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}

.markdown-content :deep(a) {
  color: var(--color-accent);
  text-decoration: underline;
}
</style>
