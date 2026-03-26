import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'
import type { Message, Conversation } from '@/types/chat'

export const chatService = {
  async getConversations(): Promise<Conversation[]> {
    const response = await axios.get(`${API_BASE_URL}/api/conversations`)
    return response.data
  },

  async getMessages(conversationId: string): Promise<Message[]> {
    const response = await axios.get(`${API_BASE_URL}/api/conversations/${conversationId}/messages`)
    return response.data
  },

  async sendMessage(conversationId: string, content: string): Promise<Message> {
    const response = await axios.post(`${API_BASE_URL}/api/conversations/${conversationId}/messages`, {
      content,
    })
    return response.data
  },

  async markAsRead(conversationId: string, messageId: string): Promise<void> {
    await axios.post(`${API_BASE_URL}/api/conversations/${conversationId}/messages/${messageId}/read`)
  },
}
