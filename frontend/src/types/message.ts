import type { Artifact } from './graph'

export interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  timestamp: Date
  artifacts?: Artifact[]
  metadata: {
    tokens_used?: number
    tool_calls?: Array<{
      tool?: string
      name?: string
      query?: string
      result_count?: number
      sources?: Array<{ title: string; url: string }>
      input?: Record<string, unknown>
    }>
    reasoning?: string
  }
}
