import { io, type Socket } from 'socket.io-client'
import { WS_URL } from '@/lib/constants'
import { formatTimestamp } from '@/lib/utils'
import { findConversation as findInStore, useChatStore } from '@/stores/useChatStore'
import {
  mapMessageStatus,
  mapRealtimeMessage,
  parseServerDate,
  type RealtimeConversation,
  type RealtimeMessage,
} from '@/services/chatMapper'
import { normalizeInstanceStatus, type InstanceStatus } from '@/services/instanceService'

const SOCKET_PATH = '/realtime/socket.io'
const SOCKET_URL = WS_URL.replace(/^ws/i, 'http')
const MAX_RECONNECT_ATTEMPTS = 5
const THINKING_CLEAR_DELAY_MS = 5000

/** O que os hooks de tela recebem do socket além do que já vai direto para o store. */
export type SocketNotice =
  | { type: 'connection'; connected: boolean }
  | { type: 'qr_code'; qrCode: string }
  | { type: 'instance_status'; status: InstanceStatus }
  /** O backend respondeu `{ok:false}`: a Instance ou a Conversation não é do usuário. */
  | { type: 'denied'; action: 'subscribe_instance' | 'join_conversation' }
  /** Chegou evento de uma Conversation que ainda não está na lista: recarregue a lista. */
  | { type: 'unknown_conversation' }
  /** Uma Conversation da lista mudou (mensagem nova): contadores e filtros podem estar defasados. */
  | { type: 'conversation_activity'; conversationId: string }

type NoticeListener = (notice: SocketNotice) => void

interface AckResponse {
  ok?: boolean
}

interface ThinkingPayload {
  conversationId?: string
  conversation_id?: string
  event: string
  data?: Record<string, unknown>
}

interface HandoffPayload {
  conversationId?: string
  conversation_id?: string
  human_in_loop?: boolean
  assigned_to?: string | null
}

/** A Conversation de um evento: o realtime a chama pelo `remote_jid`, o handoff pelo UUID. */
function findConversation(ref: string) {
  return findInStore(useChatStore.getState(), ref)
}

function isOpenByUser(conversationId: string): boolean {
  const { activeConversationId, isActiveExplicit } = useChatStore.getState()
  return isActiveExplicit && activeConversationId === conversationId
}

/** O Evolution manda o QR como texto ou como objeto `{ base64, code }`. */
function extractQrCode(payload: { qrcode?: unknown } | undefined): string | null {
  const raw = payload?.qrcode
  if (typeof raw === 'string') return raw
  if (raw && typeof raw === 'object') {
    const { base64, code } = raw as { base64?: string; code?: string }
    return base64 || code || null
  }
  return null
}

class SocketService {
  private socket: Socket | null = null
  private listeners = new Set<NoticeListener>()
  private isConnected = false
  private subscribedInstance: string | null = null
  private joined: { instanceName: string; remoteJid: string } | null = null

  /** Registra um ouvinte dos avisos do socket; devolve a função que o remove. */
  subscribe(listener: NoticeListener): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private notify(notice: SocketNotice) {
    this.listeners.forEach((listener) => listener(notice))
  }

  private emitWithAck(event: 'subscribe_instance' | 'join_conversation', data: Record<string, string>) {
    this.socket?.emit(event, data, (response?: AckResponse) => {
      if (!response?.ok) this.notify({ type: 'denied', action: event })
    })
  }

  /** Autentica pelo cookie de sessão no handshake (`withCredentials`); o token não passa pelo JavaScript. */
  connect() {
    if (this.socket?.connected) return

    this.socket?.disconnect()
    this.socket = io(SOCKET_URL, {
      withCredentials: true,
      path: SOCKET_PATH,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: MAX_RECONNECT_ATTEMPTS,
      reconnectionDelay: 1000,
    })
    this.setupEventListeners(this.socket)
  }

  private setupEventListeners(socket: Socket) {
    socket.on('connect', () => {
      this.isConnected = true
      this.notify({ type: 'connection', connected: true })
      // Depois de uma reconexão as salas se perderam: entra de novo.
      if (this.subscribedInstance) this.emitWithAck('subscribe_instance', { instanceName: this.subscribedInstance })
      if (this.joined) {
        this.emitWithAck('join_conversation', {
          instanceName: this.joined.instanceName,
          conversationId: this.joined.remoteJid,
        })
      }
    })

    socket.on('disconnect', () => {
      this.isConnected = false
      this.notify({ type: 'connection', connected: false })
    })

    socket.on('new_message', (raw: RealtimeMessage) => {
      const conversation = findConversation(raw.conversationId)
      if (!conversation) {
        this.notify({ type: 'unknown_conversation' })
        return
      }
      useChatStore.getState().addMessage(mapRealtimeMessage(raw, conversation.id))
    })

    socket.on('conversation_updated', (raw: RealtimeConversation) => {
      const conversation = findConversation(raw.id)
      if (!conversation) {
        this.notify({ type: 'unknown_conversation' })
        return
      }
      const at = parseServerDate(raw.timestamp)
      useChatStore.getState().upsertConversation({
        ...conversation,
        name: raw.name || conversation.name,
        avatar: raw.avatar || conversation.avatar,
        lastMessage: raw.lastMessage ?? conversation.lastMessage,
        timestamp: formatTimestamp(at),
        lastMessageAt: at.toISOString(),
        // A Conversation que o usuário abriu já está lida: o backend só soma `unread_count`, a UI zera.
        // A primeira da lista, aberta sozinha, continua não lida.
        unreadCount: isOpenByUser(conversation.id) ? 0 : (raw.unreadCount ?? conversation.unreadCount),
      })
      this.notify({ type: 'conversation_activity', conversationId: conversation.id })
    })

    socket.on('message_status_update', ({ messageId, status }: { messageId: string; status: string }) => {
      useChatStore.getState().updateMessageStatus(messageId, mapMessageStatus(status))
    })

    socket.on('typing', ({ conversationId, isTyping }: { conversationId: string; isTyping: boolean }) => {
      useChatStore.getState().setTyping(conversationId, isTyping)
    })

    socket.on('connection_status_update', (payload: { status?: string; evolutionState?: string }) => {
      this.notify({
        type: 'instance_status',
        status: normalizeInstanceStatus(payload.evolutionState ?? payload.status),
      })
    })

    socket.on('qr_code_update', (payload: { qrcode?: unknown }) => {
      const qrCode = extractQrCode(payload)
      if (qrCode) this.notify({ type: 'qr_code', qrCode })
    })

    socket.on('human_handoff_requested', (payload: HandoffPayload) => {
      const ref = payload.conversationId ?? payload.conversation_id
      const conversation = ref ? findConversation(ref) : undefined
      if (conversation) useChatStore.getState().setConversationHandoff(conversation.id, true)
    })

    // Assumir, devolver ou timeout: chega a todas as abas abertas da Instance.
    socket.on('handoff_updated', (payload: HandoffPayload) => {
      const ref = payload.conversationId ?? payload.conversation_id
      const conversation = ref ? findConversation(ref) : undefined
      if (conversation) {
        useChatStore
          .getState()
          .setConversationHandoff(conversation.id, payload.human_in_loop ?? false, payload.assigned_to ?? null)
      }
    })

    socket.on('thinking_event', (payload: ThinkingPayload) => {
      const ref = payload.conversationId ?? payload.conversation_id
      if (!ref) return
      const conversationId = findConversation(ref)?.id ?? ref
      const store = useChatStore.getState()

      switch (payload.event) {
        case 'thinking_start':
          store.setThinkingState(conversationId, 'indicator')
          break
        case 'thinking_token':
          if (typeof payload.data?.token === 'string') store.appendThinkingToken(conversationId, payload.data.token)
          break
        case 'thinking_end': {
          store.collapseThinking(conversationId, payload.data?.summary as string | undefined)
          const timer = setTimeout(() => useChatStore.getState().clearThinking(conversationId), THINKING_CLEAR_DELAY_MS)
          const { thinkingClearTimers } = useChatStore.getState()
          useChatStore.setState({ thinkingClearTimers: { ...thinkingClearTimers, [conversationId]: timer } })
          break
        }
      }
    })
  }

  subscribeToInstance(instanceName: string) {
    this.subscribedInstance = instanceName
    if (this.socket?.connected) this.emitWithAck('subscribe_instance', { instanceName })
  }

  leaveInstance(instanceName: string) {
    this.socket?.emit('leave_instance', { instanceName })
    if (this.subscribedInstance === instanceName) this.subscribedInstance = null
  }

  /** Entra na sala da Conversation. O backend nomeia a sala pelo `remote_jid`, não pelo UUID. */
  joinConversation(instanceName: string, remoteJid: string) {
    this.joined = { instanceName, remoteJid }
    if (this.socket?.connected) {
      this.emitWithAck('join_conversation', { instanceName, conversationId: remoteJid })
    }
  }

  leaveConversation(instanceName: string, remoteJid: string) {
    this.socket?.emit('leave_conversation', { instanceName, conversationId: remoteJid })
    if (this.joined?.remoteJid === remoteJid && this.joined.instanceName === instanceName) this.joined = null
  }

  disconnect() {
    this.socket?.disconnect()
    this.socket = null
    this.isConnected = false
    this.subscribedInstance = null
    this.joined = null
    this.notify({ type: 'connection', connected: false })
  }
}

export const socketService = new SocketService()
