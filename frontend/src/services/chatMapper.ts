import { formatTimestamp } from '@/lib/utils'
import type { ChatCounts, Conversation, Message, MessageStatus } from '@/types/chat'

/** Formas que o backend devolve em `/conversations` e `/conversations/{id}/messages`. */
export interface ContactResponse {
  name?: string | null
  push_name?: string | null
  phone_number?: string | null
  profile_pic_url?: string | null
}

export interface ConversationResponse {
  id: string
  remote_jid: string
  unread_count: number
  is_group?: boolean
  human_in_loop?: boolean
  handoff_assigned_to?: string | null
  last_message_at?: string | null
  last_message_preview?: string | null
  contact?: ContactResponse | null
}

export interface MessageResponse {
  id: string
  conversation_id?: string | null
  message_id?: string | null
  message_type: string
  content?: string | null
  caption?: string | null
  direction: string
  status: string
  is_from_me: boolean
  /** Quem falou, nas Conversations de grupo. */
  sender_name?: string | null
  timestamp: string
}

/** `GET /conversations/counts`. */
export interface CountsResponse {
  all: number
  unread: number
  groups: number
  ai: number
  human: number
  unread_messages: number
}

export interface Paginated<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

/** Eventos Socket.IO `new_message` e `conversation_updated`: o contrato é `app/realtime/events.py`, em snake_case. */
export interface RealtimeMessage {
  conversation_id: string
  message_id?: string | null
  content?: string | null
  timestamp: string
  is_outgoing: boolean
  status?: string
  sender_name?: string | null
}

export interface RealtimeConversation {
  conversation_id: string
  contact_name?: string
  last_message?: string
  timestamp: string
  unread_count?: number
  avatar?: string | null
}

const MEDIA_PLACEHOLDER: Record<string, string> = {
  image: '[Imagem]',
  video: '[Video]',
  audio: '[Audio]',
  document: '[Documento]',
  sticker: '[Sticker]',
  contact: '[Contato]',
  location: '[Localizacao]',
}

/** O backend grava `datetime.utcnow()` e serializa sem fuso: sem sufixo o JS leria como horário local. */
export function parseServerDate(value: string): Date {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

export function phoneFromJid(remoteJid: string): string {
  return remoteJid.split('@')[0]
}

export function mapMessageStatus(status?: string): MessageStatus {
  switch (status) {
    case 'read':
      return 'read'
    case 'delivered':
      return 'delivered'
    case 'sent':
      return 'sent'
    default:
      // `pending` e `failed` do servidor aparecem como relógio; `failed` na UI é só o envio que falhou aqui.
      return 'pending'
  }
}

export function mapConversation(raw: ConversationResponse): Conversation {
  const contact = raw.contact
  const lastMessageAt = raw.last_message_at ? parseServerDate(raw.last_message_at) : null
  const isGroup = raw.is_group ?? false

  return {
    id: raw.id,
    remoteJid: raw.remote_jid,
    name:
      contact?.name?.trim() ||
      contact?.push_name?.trim() ||
      contact?.phone_number ||
      phoneFromJid(raw.remote_jid),
    avatar: contact?.profile_pic_url || undefined,
    lastMessage: raw.last_message_preview ?? '',
    timestamp: lastMessageAt ? formatTimestamp(lastMessageAt) : '',
    lastMessageAt: lastMessageAt?.toISOString(),
    unreadCount: raw.unread_count ?? 0,
    isGroup,
    conversationType: isGroup ? 'group' : 'individual',
    humanHandoff: raw.human_in_loop ?? false,
    handoffAssignedTo: raw.handoff_assigned_to ?? null,
    isOnline: false,
  }
}

export function mapCounts(raw: CountsResponse): ChatCounts {
  return {
    all: raw.all,
    unread: raw.unread,
    groups: raw.groups,
    ai: raw.ai,
    human: raw.human,
    unreadMessages: raw.unread_messages,
  }
}

function messageText(type: string, content?: string | null, caption?: string | null): string {
  return content?.trim() || caption?.trim() || MEDIA_PLACEHOLDER[type] || '[Mensagem sem texto]'
}

/**
 * O id da Message na UI é o da Evolution (`message_id`) quando existe: é o que chega nos eventos
 * `new_message` e `message_status_update`, então dedup e atualização de status batem.
 */
export function mapMessage(
  raw: MessageResponse,
  conversationId: string,
  contactName: string,
  isGroup = false
): Message {
  // No grupo `contactName` é o nome do grupo: quem fala vem em `sender_name`.
  const senderName = isGroup ? raw.sender_name?.trim() || 'Participante' : contactName
  return {
    id: raw.message_id || raw.id,
    conversationId,
    content: messageText(raw.message_type, raw.content, raw.caption),
    timestamp: parseServerDate(raw.timestamp),
    isOutgoing: raw.is_from_me,
    status: mapMessageStatus(raw.status),
    messageType: 'text',
    sender: raw.is_from_me ? undefined : { name: senderName },
  }
}

export function mapRealtimeMessage(raw: RealtimeMessage, conversationId: string): Message {
  return {
    id: raw.message_id || `rt_${conversationId}_${raw.timestamp}`,
    conversationId,
    content: raw.content?.trim() || '[Mensagem sem texto]',
    timestamp: parseServerDate(raw.timestamp),
    isOutgoing: raw.is_outgoing,
    status: mapMessageStatus(raw.status),
    messageType: 'text',
    sender: raw.sender_name ? { name: raw.sender_name } : undefined,
  }
}
