import { io, Socket } from 'socket.io-client'
import { useChatStore } from '@/stores/useChatStore'
import { formatTimestamp } from '@/lib/utils'
import { chatService } from '@/services/chatService'
import type { Message, MessageStatus } from '@/types/chat'

const EVOLUTION_API_URL =
  process.env.NEXT_PUBLIC_EVOLUTION_API_URL || 'http://localhost:8081'
const EVOLUTION_API_KEY =
  process.env.NEXT_PUBLIC_EVOLUTION_API_KEY || '3v0lut10n_4P1_K3y_S3cur3_2026!'

interface EvolutionEventPayload {
  event: string
  instance: string
  data: Record<string, unknown>
  date_time?: string
  sender?: string
}

interface EvolutionMessageKey {
  remoteJid?: string
  fromMe?: boolean
  id?: string
}

interface EvolutionMessageData {
  key?: EvolutionMessageKey
  pushName?: string
  message?: Record<string, unknown>
  messageType?: string
  messageTimestamp?: number | string
  status?: string
}

interface EvolutionPresenceData {
  id?: string
  presences?: Record<
    string,
    { lastKnownPresence?: string; lastSeen?: number }[]
  >
}

const MEDIA_FALLBACK_BY_TYPE: Record<string, string> = {
  imageMessage: '[Imagem]',
  videoMessage: '[Video]',
  audioMessage: '[Audio]',
  documentMessage: '[Documento]',
  stickerMessage: '[Sticker]',
  contactMessage: '[Contato]',
  locationMessage: '[Localizacao]',
}

function extractTextFromMessage(message?: Record<string, unknown>): string {
  if (!message) return ''

  const getNestedText = (value: unknown): string => {
    if (!value || typeof value !== 'object') return ''
    const record = value as Record<string, unknown>

    if (typeof record.conversation === 'string' && record.conversation.trim())
      return record.conversation
    if (
      typeof record.text === 'string' &&
      record.text.trim() &&
      !('templateMessage' in record)
    )
      return record.text
    if (typeof record.caption === 'string' && record.caption.trim())
      return record.caption
    if (
      typeof record.selectedDisplayText === 'string' &&
      record.selectedDisplayText.trim()
    )
      return record.selectedDisplayText
    if (typeof record.title === 'string' && record.title.trim())
      return record.title

    if ('message' in record) {
      const nested = getNestedText(record.message)
      if (nested) return nested
    }

    for (const [key, nestedValue] of Object.entries(record)) {
      const nested = getNestedText(nestedValue)
      if (nested) return nested
      if (MEDIA_FALLBACK_BY_TYPE[key]) return MEDIA_FALLBACK_BY_TYPE[key]
    }
    return ''
  }

  return getNestedText(message)
}

function normalizeTimestamp(value?: number | string): Date {
  if (typeof value === 'number') return new Date(value * 1000)
  if (typeof value === 'string') {
    const asNumber = Number(value)
    if (!Number.isNaN(asNumber) && value.trim() !== '')
      return new Date(asNumber * 1000)
    return new Date(value)
  }
  return new Date()
}

function normalizeStatus(status?: string): MessageStatus {
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

function isDirectContact(remoteJid?: string): boolean {
  if (!remoteJid) return false
  return (
    !remoteJid.endsWith('@g.us') &&
    !remoteJid.endsWith('@broadcast') &&
    remoteJid !== 'status@broadcast'
  )
}

class EvolutionSocketService {
  private socket: Socket | null = null
  private isConnected = false
  private subscribedInstance: string | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private statusCheckInterval: ReturnType<typeof setInterval> | null = null

  connect() {
    if (this.socket?.connected) return

    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }

    console.log('[EvolutionWS] Connecting to Evolution API WebSocket...')

    this.socket = io(EVOLUTION_API_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: 2000,
      reconnectionDelayMax: 10000,
      extraHeaders: {
        apikey: EVOLUTION_API_KEY,
      },
    })

    this.setupListeners()
  }

  private setupListeners() {
    const socket = this.socket
    if (!socket) return

    socket.on('connect', () => {
      console.log('[EvolutionWS] Connected to Evolution API')
      this.isConnected = true
      this.reconnectAttempts = 0

      if (this.subscribedInstance) {
        socket.emit('subscribe', {
          instanceName: this.subscribedInstance,
        })
        console.log(
          '[EvolutionWS] Re-subscribed to instance:',
          this.subscribedInstance
        )
      }
    })

    socket.on('disconnect', (reason) => {
      console.log('[EvolutionWS] Disconnected:', reason)
      this.isConnected = false
    })

    socket.on('connect_error', (error) => {
      console.error('[EvolutionWS] Connection error:', error.message)
      this.reconnectAttempts++
      this.isConnected = false
    })

    // Evolution API emits events with these names
    socket.onAny((eventName: string, payload: EvolutionEventPayload) => {
      if (!this.subscribedInstance) return
      // Filter events to only the subscribed instance
      if (payload?.instance && payload.instance !== this.subscribedInstance)
        return

      switch (eventName) {
        case 'messages.upsert':
        case 'MESSAGES_UPSERT':
          this.handleMessageUpsert(payload)
          break
        case 'messages.update':
        case 'MESSAGES_UPDATE':
          this.handleMessageUpdate(payload)
          break
        case 'chats.upsert':
        case 'CHATS_UPSERT':
        case 'chats.update':
        case 'CHATS_UPDATE':
          this.handleChatUpdate(payload)
          break
        case 'presence.update':
        case 'PRESENCE_UPDATE':
          this.handlePresenceUpdate(payload)
          break
        case 'connection.update':
        case 'CONNECTION_UPDATE':
          this.handleConnectionUpdate(payload)
          break
      }
    })
  }

  private handleMessageUpsert(payload: EvolutionEventPayload) {
    const data = payload.data as unknown as EvolutionMessageData
    if (!data?.key?.remoteJid) return
    if (!isDirectContact(data.key.remoteJid)) return

    const remoteJid = data.key.remoteJid
    const content =
      extractTextFromMessage(data.message) || '[Mensagem sem texto]'
    const isOutgoing = Boolean(data.key.fromMe)

    const message: Message = {
      id:
        data.key.id ||
        `${remoteJid}-${data.messageTimestamp || Date.now()}`,
      conversationId: remoteJid,
      content,
      timestamp: normalizeTimestamp(data.messageTimestamp),
      isOutgoing,
      status: normalizeStatus(data.status),
      messageType: 'text',
      sender: isOutgoing
        ? undefined
        : { name: data.pushName || remoteJid.split('@')[0] || 'Contato' },
    }

    const { addMessage, updateConversationLastMessage, incrementUnreadCount, activeConversationId } =
      useChatStore.getState()

    addMessage(message)
    updateConversationLastMessage(
      remoteJid,
      content,
      formatTimestamp(message.timestamp)
    )

    // Increment unread if this message is not from the active conversation
    if (!isOutgoing && remoteJid !== activeConversationId) {
      incrementUnreadCount(remoteJid)
    }
  }

  private handleMessageUpdate(payload: EvolutionEventPayload) {
    const data = payload.data as unknown as EvolutionMessageData
    if (!data?.key?.id) return

    const status = normalizeStatus(data.status)
    const { updateMessageStatus } = useChatStore.getState()
    updateMessageStatus(data.key.id, status)
  }

  private handleChatUpdate(_payload: EvolutionEventPayload) {
    // Refresh conversations list when chats are updated
    if (!this.subscribedInstance) return
    void chatService
      .getConversations(this.subscribedInstance)
      .then((response) => {
        const { setConversations } = useChatStore.getState()
        setConversations(response.items)
      })
      .catch((error) => {
        console.error('[EvolutionWS] Failed to refresh conversations:', error)
      })
  }

  private handlePresenceUpdate(payload: EvolutionEventPayload) {
    const data = payload.data as unknown as EvolutionPresenceData
    if (!data?.id || !data.presences) return

    const remoteJid = data.id
    const presenceValues = Object.values(data.presences).flat()
    const isTyping = presenceValues.some(
      (p) => p.lastKnownPresence === 'composing'
    )

    const { setTyping } = useChatStore.getState()
    setTyping(remoteJid, isTyping)
  }

  private handleConnectionUpdate(payload: EvolutionEventPayload) {
    const data = payload.data as Record<string, unknown>
    console.log('[EvolutionWS] Connection update:', data)
  }

  subscribeToInstance(instanceName: string) {
    this.subscribedInstance = instanceName

    if (this.socket?.connected) {
      this.socket.emit('subscribe', { instanceName })
      console.log('[EvolutionWS] Subscribed to instance:', instanceName)
    }
  }

  leaveInstance(instanceName: string) {
    if (this.socket?.connected) {
      this.socket.emit('unsubscribe', { instanceName })
    }
    if (this.subscribedInstance === instanceName) {
      this.subscribedInstance = null
    }
  }

  getConnectionStatus(): boolean {
    return this.isConnected
  }

  disconnect() {
    if (this.statusCheckInterval) {
      clearInterval(this.statusCheckInterval)
      this.statusCheckInterval = null
    }
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
    this.isConnected = false
    this.subscribedInstance = null
  }
}

export const evolutionSocketService = new EvolutionSocketService()
