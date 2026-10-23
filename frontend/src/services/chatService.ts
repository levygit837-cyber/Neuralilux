import { CONVERSATION_PAGE_SIZE, MESSAGE_PAGE_SIZE } from '@/lib/constants'
import { apiRequest, jsonBody } from '@/services/http'
import {
  mapConversation,
  mapCounts,
  mapMessage,
  type ConversationResponse,
  type CountsResponse,
  type MessageResponse,
  type Paginated,
} from '@/services/chatMapper'
import type { ChatCounts, Conversation, ConversationCategory, Message } from '@/types/chat'

/** Estado do Handoff devolvido pelas rotas de assumir e devolver. */
export interface HandoffState {
  human_in_loop: boolean
  assigned_to: string | null
}

/** O que a importação do histórico criou. */
export interface SyncResult {
  conversations: number
  messages: number
}

export interface ConversationQuery {
  category?: ConversationCategory
  search?: string
  /** Quantas Conversations pular; a página tem `CONVERSATION_PAGE_SIZE`. */
  skip?: number
}

/** Uma página da lista e o total que o filtro tem no servidor. */
export interface ConversationPage {
  conversations: Conversation[]
  total: number
}

export const chatService = {
  /** Conversations de uma Instance. `instanceId` é o UUID local, não o nome na Evolution. */
  async getConversations(
    instanceId: string,
    { category = 'all', search = '', skip = 0 }: ConversationQuery = {}
  ): Promise<ConversationPage> {
    // `is_archived=false` alinha a lista com `/conversations/counts`, que não conta arquivadas.
    const query = new URLSearchParams({
      instance_id: instanceId,
      is_archived: 'false',
      limit: String(CONVERSATION_PAGE_SIZE),
    })
    if (skip > 0) query.set('skip', String(skip))
    if (category !== 'all') query.set('category', category)
    if (search.trim()) query.set('search', search.trim())
    const response = await apiRequest<Paginated<ConversationResponse>>(
      `/conversations?${query}`,
      {},
      'Falha ao carregar as conversas'
    )
    return { conversations: response.items.map(mapConversation), total: response.total }
  },

  /** Quantas Conversations cada filtro devolve; a lista pode ter só uma delas. */
  async getCounts(instanceId: string): Promise<ChatCounts> {
    const query = new URLSearchParams({ instance_id: instanceId })
    const response = await apiRequest<CountsResponse>(
      `/conversations/counts?${query}`,
      {},
      'Falha ao carregar os contadores das conversas'
    )
    return mapCounts(response)
  },

  /** Zera as não lidas no servidor; a UI zera a cópia local por conta própria. */
  async markRead(conversationId: string): Promise<void> {
    await apiRequest<{ unread_count: number }>(
      `/conversations/${conversationId}/read`,
      { method: 'POST' },
      'Falha ao marcar a conversa como lida'
    )
  },

  /** Importa o histórico da Evolution para a Instance (síncrono, pode levar alguns segundos). */
  syncHistory(instanceId: string): Promise<SyncResult> {
    const query = new URLSearchParams({ instance_id: instanceId })
    return apiRequest<SyncResult>(
      `/conversations/sync?${query}`,
      { method: 'POST' },
      'Falha ao sincronizar o histórico'
    )
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
      .map((raw) => mapMessage(raw, conversation.id, conversation.name, conversation.isGroup))
      .reverse()
  },

  /** O Attendant assume a Conversation: o Agent para de responder. */
  takeControl(conversationId: string): Promise<HandoffState> {
    return apiRequest<HandoffState>(
      `/conversations/${conversationId}/take-control`,
      jsonBody('POST', {}),
      'Falha ao assumir a conversa'
    )
  },

  /** Devolve a Conversation ao Agent e fecha o Ticket. */
  releaseControl(conversationId: string): Promise<HandoffState> {
    return apiRequest<HandoffState>(
      `/conversations/${conversationId}/release-control`,
      { method: 'POST' },
      'Falha ao devolver a conversa ao Agent'
    )
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
