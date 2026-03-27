import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'
import { getCookie } from '@/lib/cookieStorage'
import type { Message, Conversation } from '@/types/chat'

// Create axios instance with auth interceptor
const api = axios.create({
  baseURL: API_BASE_URL,
})

// Add auth token to requests (token is stored in cookies via Zustand persist)
api.interceptors.request.use((config) => {
  try {
    // Try to get token from Zustand persisted cookie storage
    const authStorage = getCookie('auth-storage')
    if (authStorage) {
      const parsed = JSON.parse(authStorage)
      const token = parsed?.state?.token
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
  } catch (error) {
    console.warn('Failed to get auth token:', error)
  }
  return config
})

export const chatService = {
  async getConversations(): Promise<Conversation[]> {
    const response = await api.get('/api/v1/conversations')
    // Backend returns paginated response: { items: [...], total, skip, limit }
    const paginatedData = response.data
    const backendConversations = paginatedData.items || paginatedData
    
    // Transform backend conversation format to frontend format
    return backendConversations.map((conv: any) => ({
      id: conv.id,
      name: conv.contact?.name || conv.contact_name || conv.remote_jid?.split('@')[0] || 'Unknown',
      avatar: conv.contact?.profile_pic_url || conv.contact_avatar,
      lastMessage: conv.last_message_preview || '',
      timestamp: conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '',
      unreadCount: conv.unread_count || 0,
      isOnline: false, // Backend doesn't provide this info directly
    }))
  },

  async getMessages(conversationId: string): Promise<Message[]> {
    const response = await api.get(`/api/v1/conversations/${conversationId}/messages`)
    // Backend returns paginated response: { items: [...], total, skip, limit }
    const paginatedData = response.data
    const messages = paginatedData.items || paginatedData
    
    // Transform backend message format to frontend format
    return messages.map((msg: any) => ({
      id: msg.id || msg.message_id,
      conversationId: conversationId,
      content: msg.content || msg.caption || '',
      timestamp: new Date(msg.timestamp || msg.created_at),
      isOutgoing: msg.is_from_me || msg.direction === 'outgoing',
      status: msg.status || 'sent',
      sender: msg.sender,
    }))
  },

  async sendMessage(conversationId: string, content: string): Promise<Message> {
    const response = await api.post(`/api/v1/conversations/${conversationId}/messages`, {
      content,
      message_type: 'text',
    })
    // Backend returns SendMessageResponse, transform to Message format
    const data = response.data
    return {
      id: data.message_id || data.id,
      conversationId: conversationId,
      content: content,
      timestamp: new Date(),
      isOutgoing: true,
      status: data.status || 'sent',
    }
  },

  async markAsRead(conversationId: string, messageId: string): Promise<void> {
    await api.post(`/api/v1/conversations/${conversationId}/messages/${messageId}/read`)
  },
}
