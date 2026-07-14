export interface Note {
  id: string
  user_id: string
  title: string
  content: string
  created_at: string
  updated_at: string
}

export interface NoteSummary {
  id: string
  title: string
  preview: string
  updated_at: string
}

export interface NoteSuggestion {
  suggestion: string
  original_input: string
  noteId: string
}
