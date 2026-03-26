export type MessageStatus = 'pending' | 'sending' | 'sent' | 'delivered' | 'read'

export interface Message {
  id: string
  conversationId: string
  content: string
  timestamp: Date
  isOutgoing: boolean
  status: MessageStatus
  sender?: {
    name: string
    avatar?: string
  }
}

export interface Conversation {
  id: string
  name: string
  avatar?: string
  lastMessage: string
  timestamp: string
  unreadCount: number
  isOnline?: boolean
}

export interface TypingIndicator {
  conversationId: string
  isTyping: boolean
}
