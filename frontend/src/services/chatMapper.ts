import { formatTimestamp } from '@/lib/utils'
import type { Conversation, Message, MessageStatus } from '@/types/chat'

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
  timestamp: string
}

export interface Paginated<T> {
  items: T[]
  total: number
  skip: number
  limit: number
}

/** Forma dos eventos Socket.IO `new_message` e `conversation_updated` (ver `status_events.publish_message`). */
export interface RealtimeMessage {
  id?: string | null
  conversationId: string
  content?: string | null
  timestamp: string
  isOutgoing: boolean
  status?: string
  sender?: { name: string } | null
}

export interface RealtimeConversation {
  id: string
  name?: string
  lastMessage?: string
  timestamp: string
  unreadCount?: number
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
    humanHandoff: raw.human_in_loop ?? false,
    handoffAssignedTo: raw.handoff_assigned_to ?? null,
    isOnline: false,
  }
}

function messageText(type: string, content?: string | null, caption?: string | null): string {
  return content?.trim() || caption?.trim() || MEDIA_PLACEHOLDER[type] || '[Mensagem sem texto]'
}

/**
 * O id da Message na UI é o da Evolution (`message_id`) quando existe: é o que chega nos eventos
 * `new_message` e `message_status_update`, então dedup e atualização de status batem.
 */
export function mapMessage(raw: MessageResponse, conversationId: string, contactName: string): Message {
  return {
    id: raw.message_id || raw.id,
    conversationId,
    content: messageText(raw.message_type, raw.content, raw.caption),
    timestamp: parseServerDate(raw.timestamp),
    isOutgoing: raw.is_from_me,
    status: mapMessageStatus(raw.status),
    messageType: 'text',
    sender: raw.is_from_me ? undefined : { name: contactName },
  }
}

/** `conversationId` já é o UUID: o evento traz o `remote_jid`, quem chama resolve antes. */
export function mapRealtimeMessage(raw: RealtimeMessage, conversationId: string): Message {
  return {
    id: raw.id || `rt_${conversationId}_${raw.timestamp}`,
    conversationId,
    content: raw.content?.trim() || '[Mensagem sem texto]',
    timestamp: parseServerDate(raw.timestamp),
    isOutgoing: raw.isOutgoing,
    status: mapMessageStatus(raw.status),
    messageType: 'text',
    sender: raw.sender ?? undefined,
  }
}
