import axios from 'axios'
import { formatTimestamp } from '@/lib/utils'
import type { Conversation, Message, MessageStatus } from '@/types/chat'

const EVOLUTION_API_URL =
  process.env.NEXT_PUBLIC_EVOLUTION_API_URL || 'http://localhost:8081'
const EVOLUTION_API_KEY =
  process.env.NEXT_PUBLIC_EVOLUTION_API_KEY || '3v0lut10n_4P1_K3y_S3cur3_2026!'

const evolutionApi = axios.create({
  baseURL: EVOLUTION_API_URL,
  headers: {
    apikey: EVOLUTION_API_KEY,
    'Content-Type': 'application/json',
  },
})

interface EvolutionContact {
  remoteJid?: string
  pushName?: string
  profilePicUrl?: string | null
}

interface EvolutionChat {
  remoteJid?: string
  pushName?: string
  profilePicUrl?: string | null
  updatedAt?: string
  unreadCount?: number
  lastMessage?: EvolutionMessageRecord
}

interface EvolutionMessageRecord {
  id?: string
  key?: {
    id?: string
    fromMe?: boolean
    remoteJid?: string
  }
  pushName?: string
  message?: Record<string, unknown>
  messageTimestamp?: number | string
  status?: string
}

interface EvolutionMessagesResponse {
  messages?: {
    total?: number
    records?: EvolutionMessageRecord[]
  }
}

export interface ConversationsResponse {
  items: Conversation[]
  total: number
  skip: number
  limit: number
}

export interface MessagesResponse {
  items: Message[]
  total: number
  skip: number
  limit: number
}

const MEDIA_FALLBACK_BY_TYPE: Record<string, string> = {
  imageMessage: '[Imagem]',
  videoMessage: '[Video]',
  audioMessage: '[Audio]',
  documentMessage: '[Documento]',
  stickerMessage: '[Sticker]',
  contactMessage: '[Contato]',
  locationMessage: '[Localizacao]',
  liveLocationMessage: '[Localizacao ao vivo]',
}

function isDirectContact(remoteJid?: string): remoteJid is string {
  if (!remoteJid) {
    return false
  }

  return (
    !remoteJid.endsWith('@g.us') &&
    !remoteJid.endsWith('@broadcast') &&
    remoteJid !== 'status@broadcast'
  )
}

function extractPhone(remoteJid?: string): string {
  if (!remoteJid) {
    return 'Contato'
  }

  return remoteJid.split('@')[0] || remoteJid
}

function extractDisplayName(
  remoteJid?: string,
  primaryName?: string | null,
  fallbackName?: string | null
): string {
  return primaryName?.trim() || fallbackName?.trim() || extractPhone(remoteJid)
}

function extractMessageText(message?: Record<string, unknown>): string {
  if (!message) {
    return ''
  }

  const getNestedText = (value: unknown): string => {
    if (!value || typeof value !== 'object') {
      return ''
    }

    const record = value as Record<string, unknown>

    if (typeof record.conversation === 'string' && record.conversation.trim()) {
      return record.conversation
    }

    if (
      typeof record.text === 'string' &&
      record.text.trim() &&
      !('templateMessage' in record)
    ) {
      return record.text
    }

    if (typeof record.caption === 'string' && record.caption.trim()) {
      return record.caption
    }

    if (
      typeof record.selectedDisplayText === 'string' &&
      record.selectedDisplayText.trim()
    ) {
      return record.selectedDisplayText
    }

    if (typeof record.title === 'string' && record.title.trim()) {
      return record.title
    }

    if (typeof record.name === 'string' && record.name.trim()) {
      return record.name
    }

    if ('message' in record) {
      const nested = getNestedText(record.message)
      if (nested) {
        return nested
      }
    }

    for (const [key, nestedValue] of Object.entries(record)) {
      const nested = getNestedText(nestedValue)
      if (nested) {
        return nested
      }

      if (MEDIA_FALLBACK_BY_TYPE[key]) {
        return MEDIA_FALLBACK_BY_TYPE[key]
      }
    }

    return ''
  }

  return getNestedText(message)
}

function normalizeMessageStatus(status?: string): MessageStatus {
  switch (status) {
    case 'READ':
    case 'read':
      return 'read'
    case 'DELIVERY_ACK':
    case 'delivered':
      return 'delivered'
    case 'SERVER_ACK':
    case 'sent':
      return 'sent'
    case 'PENDING':
    case 'pending':
      return 'pending'
    default:
      return 'sent'
  }
}

function normalizeTimestamp(value?: number | string): Date {
  if (typeof value === 'number') {
    return new Date(value * 1000)
  }

  if (typeof value === 'string') {
    const asNumber = Number(value)
    if (!Number.isNaN(asNumber) && value.trim() !== '') {
      return new Date(asNumber * 1000)
    }

    return new Date(value)
  }

  return new Date()
}

function mapConversation(
  remoteJid: string,
  contact?: EvolutionContact,
  chat?: EvolutionChat
): Conversation {
  const updatedAt = chat?.updatedAt ? new Date(chat.updatedAt) : null

  return {
    id: remoteJid,
    name: extractDisplayName(remoteJid, contact?.pushName, chat?.pushName),
    avatar: contact?.profilePicUrl || chat?.profilePicUrl || undefined,
    lastMessage: extractMessageText(chat?.lastMessage?.message) || '',
    timestamp: updatedAt ? formatTimestamp(updatedAt) : '',
    unreadCount: chat?.unreadCount || 0,
    isOnline: false,
  }
}

function mapMessage(remoteJid: string, record: EvolutionMessageRecord): Message {
  const content = extractMessageText(record.message) || '[Mensagem sem texto]'
  const isOutgoing = Boolean(record.key?.fromMe)

  return {
    id: record.key?.id || record.id || `${remoteJid}-${record.messageTimestamp || Date.now()}`,
    conversationId: remoteJid,
    content,
    timestamp: normalizeTimestamp(record.messageTimestamp),
    isOutgoing,
    status: normalizeMessageStatus(record.status),
    sender: isOutgoing
      ? undefined
      : {
          name: extractDisplayName(remoteJid, record.pushName),
        },
  }
}

function buildSortedConversations(
  contacts: EvolutionContact[],
  chats: EvolutionChat[]
): Conversation[] {
  const contactsByJid = new Map<string, EvolutionContact>()
  const chatsByJid = new Map<string, EvolutionChat>()

  contacts.filter((contact) => isDirectContact(contact.remoteJid)).forEach((contact) => {
    contactsByJid.set(contact.remoteJid!, contact)
  })

  chats.filter((chat) => isDirectContact(chat.remoteJid)).forEach((chat) => {
    chatsByJid.set(chat.remoteJid!, chat)
  })

  const remoteJids = new Set<string>([
    ...contactsByJid.keys(),
    ...chatsByJid.keys(),
  ])

  return Array.from(remoteJids)
    .map((remoteJid) =>
      mapConversation(remoteJid, contactsByJid.get(remoteJid), chatsByJid.get(remoteJid))
    )
    .sort((first, second) => {
      const firstUpdatedAt = chatsByJid.get(first.id)?.updatedAt
      const secondUpdatedAt = chatsByJid.get(second.id)?.updatedAt

      if (firstUpdatedAt && secondUpdatedAt) {
        return new Date(secondUpdatedAt).getTime() - new Date(firstUpdatedAt).getTime()
      }

      if (secondUpdatedAt) {
        return 1
      }

      if (firstUpdatedAt) {
        return -1
      }

      return first.name.localeCompare(second.name, 'pt-BR')
    })
}

export const chatService = {
  async getConversations(instanceName: string): Promise<ConversationsResponse> {
    const [contactsResponse, chatsResponse] = await Promise.all([
      evolutionApi.post<EvolutionContact[]>(`/chat/findContacts/${instanceName}`, {}),
      evolutionApi.post<EvolutionChat[]>(`/chat/findChats/${instanceName}`, {}),
    ])

    const contacts = Array.isArray(contactsResponse.data) ? contactsResponse.data : []
    const chats = Array.isArray(chatsResponse.data) ? chatsResponse.data : []
    const items = buildSortedConversations(contacts, chats)

    return {
      items,
      total: items.length,
      skip: 0,
      limit: items.length,
    }
  },

  async getMessages(
    instanceName: string,
    remoteJid: string,
    params?: { limit?: number }
  ): Promise<MessagesResponse> {
    const response = await evolutionApi.post<EvolutionMessagesResponse>(
      `/chat/findMessages/${instanceName}`,
      {
        where: {
          key: {
            remoteJid,
          },
        },
        limit: params?.limit ?? 50,
      }
    )

    const records = response.data.messages?.records || []
    const items = records
      .map((record) => mapMessage(remoteJid, record))
      .sort((first, second) => first.timestamp.getTime() - second.timestamp.getTime())

    return {
      items,
      total: response.data.messages?.total ?? items.length,
      skip: 0,
      limit: params?.limit ?? 50,
    }
  },

  async sendMessage(
    instanceName: string,
    remoteJid: string,
    content: string
  ): Promise<{
    success: boolean
    message_id: string
    status: string
    message: string
  }> {
    const response = await evolutionApi.post(`/message/sendText/${instanceName}`, {
      number: extractPhone(remoteJid),
      text: content,
      options: {
        delay: 1200,
        presence: 'composing',
      },
    })

    return {
      success: true,
      message_id: response.data?.key?.id || response.data?.id || '',
      status: response.data?.status || 'sent',
      message: 'Mensagem enviada',
    }
  },

  async markAsRead(): Promise<void> {
    // Evolution API chat endpoints used here do not expose a compatible read endpoint in this frontend flow.
  },
}
