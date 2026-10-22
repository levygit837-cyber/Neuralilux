import { CONVERSATION_PAGE_SIZE, MESSAGE_PAGE_SIZE } from '@/lib/constants'
import { apiRequest, jsonBody } from '@/services/http'
import {
  mapConversation,
  mapMessage,
  type ConversationResponse,
  type MessageResponse,
  type Paginated,
} from '@/services/chatMapper'
import type { Conversation, Message } from '@/types/chat'

export const chatService = {
  /** Conversations de uma Instance. `instanceId` é o UUID local, não o nome na Evolution. */
  async getConversations(instanceId: string): Promise<Conversation[]> {
    const query = new URLSearchParams({ instance_id: instanceId, limit: String(CONVERSATION_PAGE_SIZE) })
    const response = await apiRequest<Paginated<ConversationResponse>>(
      `/conversations?${query}`,
      {},
      'Falha ao carregar as conversas'
    )
    return response.items.map(mapConversation)
  },

  /** Histórico em ordem cronológica (a API devolve do mais novo para o mais antigo). */
  async getMessages(conversation: Conversation): Promise<Message[]> {
    const query = new URLSearchParams({ limit: String(MESSAGE_PAGE_SIZE) })
    const response = await apiRequest<Paginated<MessageResponse>>(
      `/conversations/${conversation.id}/messages?${query}`,
      {},
      'Falha ao carregar as mensagens'
    )
    return response.items
      .map((raw) => mapMessage(raw, conversation.id, conversation.name))
      .reverse()
  },

  /** Devolve o id da Message na Evolution, o mesmo que os eventos realtime usam. */
  async sendMessage(conversationId: string, content: string): Promise<string | null> {
    const response = await apiRequest<{ message_id: string | null }>(
      `/conversations/${conversationId}/messages`,
      jsonBody('POST', { content, message_type: 'text' }),
      'Falha ao enviar a mensagem'
    )
    return response.message_id
  },
}
