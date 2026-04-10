export type MessageStatus = 'pending' | 'sending' | 'sent' | 'delivered' | 'read'

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
  id: string
  name: string
  avatar?: string
  lastMessage: string
  timestamp: string
  unreadCount: number
  isOnline?: boolean
  isTyping?: boolean
  isGroup?: boolean
  isBot?: boolean
  groupAvatars?: string[]
  conversationType?: ConversationType
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

export type ContactFilter = 'all' | 'unread' | 'groups' | 'ai-active'