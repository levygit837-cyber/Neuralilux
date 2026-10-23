export type MessageStatus = 'pending' | 'sending' | 'sent' | 'delivered' | 'read' | 'failed'

export type MessageType = 'text' | 'audio' | 'image' | 'video' | 'system'

export type ThinkingState = 'idle' | 'indicator' | 'streaming' | 'collapsed'

export type ConversationType = 'individual' | 'group'

export interface AudioMetadata {
  duration: number
  waveform?: number[]
  url?: string
}

export interface ImageMetadata {
  url: string
  width?: number
  height?: number
  caption?: string
}

export interface VideoMetadata {
  url: string
  duration: number
  width?: number
  height?: number
  thumbnailUrl?: string
}

export interface SystemMessageMetadata {
  type: 'ai-takeover' | 'agent-handover' | 'system-notice'
  agentName?: string
  message?: string
}

export interface Message {
  id: string
  conversationId: string
  content: string
  timestamp: Date
  isOutgoing: boolean
  status: MessageStatus
  messageType: MessageType
  sender?: {
    name: string
    avatar?: string
  }
  audioMetadata?: AudioMetadata
  imageMetadata?: ImageMetadata
  videoMetadata?: VideoMetadata
  systemMetadata?: SystemMessageMetadata
}

export interface Conversation {
  /** UUID da Conversation no backend. Os eventos realtime a identificam pelo `remoteJid`. */
  id: string
  remoteJid: string
  name: string
  avatar?: string
  lastMessage: string
  /** Horário já formatado para a lista. */
  timestamp: string
  /** ISO 8601 do último movimento; é a chave de ordenação. */
  lastMessageAt?: string
  unreadCount: number
  isOnline?: boolean
  isTyping?: boolean
  isGroup?: boolean
  isBot?: boolean
  groupAvatars?: string[]
  conversationType?: ConversationType
  /** A Conversation está com um Attendant (eventos `human_handoff_requested` e `handoff_updated`). */
  humanHandoff?: boolean
  /** Id do usuário que assumiu o Handoff; null enquanto o Ticket espera alguém. */
  handoffAssignedTo?: string | null
}

export interface TypingIndicator {
  conversationId: string
  isTyping: boolean
}

export interface ThinkingEvent {
  conversationId: string
  state: ThinkingState
  tokens?: string[]
  summary?: string
  startedAt?: Date
}

/** Filtro da lista de Conversations; é o `category` aceito por `GET /conversations`. */
export type ConversationCategory = 'all' | 'unread' | 'groups' | 'ai' | 'human'

/** Quantas Conversations cada filtro devolve, mais o total de Messages não lidas. */
export interface ChatCounts {
  all: number
  unread: number
  groups: number
  ai: number
  human: number
  unreadMessages: number
}

export interface AgentListItem {
  id: string
  name: string
  description?: string | null
}
