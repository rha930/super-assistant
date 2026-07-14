<template>
  <div class="flex-1 flex flex-col overflow-hidden">
    <!-- Title -->
    <div class="px-4 py-2 border-b app-border">
      <input
        :value="note.title"
        @input="$emit('update:title', ($event.target as HTMLInputElement).value)"
        class="w-full text-sm font-semibold app-text app-surface bg-transparent border-none outline-none"
        placeholder="Note title..."
        maxlength="200"
      />
    </div>

    <!-- Tab bar: Edit / Preview -->
    <div class="px-4 pt-2 flex gap-2 border-b app-border">
      <button
        @click="viewMode = 'edit'"
        :class="[
          'px-3 py-1 text-xs rounded-t-md transition-colors',
          viewMode === 'edit'
            ? 'app-surface font-semibold app-text border border-b-0 app-border'
            : 'app-text-muted hover:opacity-80'
        ]"
      >
        Edit
      </button>
      <button
        @click="viewMode = 'preview'"
        :class="[
          'px-3 py-1 text-xs rounded-t-md transition-colors',
          viewMode === 'preview'
            ? 'app-surface font-semibold app-text border border-b-0 app-border'
            : 'app-text-muted hover:opacity-80'
        ]"
      >
        Preview
      </button>
      <div class="flex-1"></div>
      <button
        @click="$emit('save')"
        class="px-3 py-1 text-xs btn-primary rounded-md mb-1"
        title="Save (Cmd/Ctrl+S)"
      >
        Save
      </button>
    </div>

    <!-- Editor -->
    <div v-if="viewMode === 'edit'" class="flex-1 overflow-hidden">
      <textarea
        ref="editorRef"
        :value="note.content"
        @input="$emit('update:content', ($event.target as HTMLTextAreaElement).value)"
        @keydown="handleKeydown"
        class="w-full h-full p-4 app-surface app-text text-sm font-mono resize-none outline-none border-none"
        placeholder="Start writing... (Markdown supported)"
      ></textarea>
    </div>

    <!-- Preview -->
    <div
      v-else
      class="flex-1 overflow-y-auto p-4 markdown-content app-text text-sm"
      v-html="renderedContent"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Note } from '../types/note'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

interface Props {
  note: Note
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:title': [value: string]
  'update:content': [value: string]
  save: []
}>()

const viewMode = ref<'edit' | 'preview'>('edit')
const editorRef = ref<HTMLTextAreaElement>()

marked.setOptions({ breaks: true, gfm: true })

const renderedContent = computed(() => {
  const raw = props.note.content || ''
  const html = marked.parse(raw) as string
  return DOMPurify.sanitize(html)
})

function handleKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === 's') {
    e.preventDefault()
    emit('save')
  }
}
</script>

<style scoped>
.markdown-content :deep(p) { margin: 0.25rem 0; }
.markdown-content :deep(ul),
.markdown-content :deep(ol) { padding-left: 1.25rem; margin: 0.25rem 0; }
.markdown-content :deep(h1) { font-size: 1.5rem; font-weight: 700; margin: 0.75rem 0 0.25rem; }
.markdown-content :deep(h2) { font-size: 1.25rem; font-weight: 600; margin: 0.5rem 0 0.25rem; }
.markdown-content :deep(h3) { font-size: 1.1rem; font-weight: 600; margin: 0.5rem 0 0.25rem; }
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
  border: 1px solid var(--color-border);
}
.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
}
</style>
