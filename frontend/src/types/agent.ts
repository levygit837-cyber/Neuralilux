export type AgentMessageBlockType =
  | 'message'
  | 'thinking_indicator'
  | 'thinking_streaming'
  | 'thinking_collapsed'
  | 'tool_result'

export type AgentToolPhase = 'waiting_input' | 'started' | 'completed' | 'failed'

export interface AgentToolEvent {
  traceId?: string
  requestId?: string
  source?: string
  toolName: string
  displayName?: string
  phase: AgentToolPhase
  inputPreview?: string
  outputPreview?: string
  inputPayload?: Record<string, unknown> | null
  outputPayload?: unknown
  error?: string
  startedAt?: string
  finishedAt?: string
  isLive?: boolean
  persistedAt?: string
}

export interface AgentMessage {
  id: string
  content: string
  timestamp: Date
  isAgent: boolean
  blockType?: AgentMessageBlockType
  thinkingContent?: string
  thinkingSummary?: string
  thinkingTokens?: string[]
  thinkingLive?: boolean
  streaming?: boolean
  toolEvent?: AgentToolEvent
}

export interface AgentSessionMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content?: string | null
  tool_name?: string | null
  tool_input?: Record<string, unknown> | null
  tool_output?: string | null
  thinking_content?: string | null
  metadata?: Record<string, unknown> | null
  created_at: string
}

export interface AgentSessionSummary {
  id: string
  company_id: string
  user_id: string
  title?: string | null
  is_active: boolean
  interaction_count: number
  last_checkpoint_at: number
  last_message_preview?: string | null
  created_at: string
  updated_at?: string | null
}

export interface AgentListItem {
  id: string
  name: string
  description?: string | null
}
