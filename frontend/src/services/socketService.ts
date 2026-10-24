import { io, type Socket } from 'socket.io-client'
import { WS_URL } from '@/lib/constants'
import { formatTimestamp } from '@/lib/utils'
import { queryKeys } from '@/lib/queryKeys'
import { getQueryClient } from '@/lib/queryClient'
import { cancelThinkingClear, scheduleThinkingClear } from '@/lib/thinkingTimers'
import { endSession } from '@/services/http'
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
/** Reconexão sem limite de tentativas: o intervalo cresce até o teto e fica nele (o backend pode ficar fora por minutos). */
const RECONNECT_DELAY_MS = 1000
const RECONNECT_DELAY_MAX_MS = 10_000
/** Mensagem do `connect_error` quando o backend recusa a sessão do handshake (ver `ConnectionRefusedError` em `realtime/socket.py`). */
const UNAUTHORIZED = 'unauthorized'

/** O que os hooks de tela recebem do socket além do que já vai direto para o store. */
export type SocketNotice =
  | { type: 'connection'; connected: boolean }
  /** O socket voltou depois de uma queda: o que chegou enquanto estava fora se perdeu, recarregue. */
  | { type: 'reconnected' }
  | { type: 'qr_code'; qrCode: string }
  | { type: 'instance_status'; status: InstanceStatus }
  /** O backend respondeu `{ok:false}`: a Instance ou a Conversation não é do usuário. */
  | { type: 'denied'; action: 'subscribe_instance' | 'join_conversation' }
  /** Chegou evento de uma Conversation que ainda não está na lista: recarregue a lista. */
  | { type: 'unknown_conversation' }
  /** Uma Conversation da lista mudou (mensagem nova): contadores e filtros podem estar defasados. */
  | { type: 'conversation_activity'; conversationId: string }

type NoticeListener = (notice: SocketNotice) => void

/** Estado da conexão para a UI. `degraded`: caiu ou falhou depois de ter tentado; some quando reconecta. */
export interface SocketState {
  connected: boolean
  degraded: boolean
}

interface AckResponse {
  ok?: boolean
}

interface ThinkingPayload {
  conversation_id: string
  event: 'thinking_start' | 'thinking_end'
  data?: { summary?: string }
}

interface HandoffPayload {
  conversation_id: string
  human_in_loop?: boolean
  assigned_to?: string | null
}

function findConversation(id: string) {
  return findInStore(useChatStore.getState(), id)
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

const joinKey = (instanceId: string, conversationId: string) => `${instanceId}:${conversationId}`

function count(map: Map<string, number>, key: string, delta: 1 | -1): number {
  const next = (map.get(key) ?? 0) + delta
  if (next > 0) map.set(key, next)
  else map.delete(key)
  return Math.max(next, 0)
}

/**
 * Um socket para o painel todo. Quem liga e desliga é o `RealtimeProvider` do layout `(app)`; as telas só
 * declaram o que querem receber (`subscribeToInstance`, `joinConversation`), por contagem: duas telas
 * na mesma Instance não se atrapalham, e sair de uma não derruba a outra.
 */
class SocketService {
  private socket: Socket | null = null
  private listeners = new Set<NoticeListener>()
  private stateListeners = new Set<() => void>()
  private state: SocketState = { connected: false, degraded: false }
  private hasConnected = false
  /** Interesse das telas: refeito inteiro a cada `connect`, porque as salas do servidor somem na queda. */
  private instances = new Map<string, number>()
  private conversations = new Map<string, number>()

  /** Registra um ouvinte dos avisos do socket; devolve a função que o remove. */
  subscribe(listener: NoticeListener): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  /** Para `useSyncExternalStore`: o snapshot só muda de identidade quando o estado muda. */
  subscribeState = (listener: () => void): (() => void) => {
    this.stateListeners.add(listener)
    return () => {
      this.stateListeners.delete(listener)
    }
  }

  getState = (): SocketState => this.state

  private setState(patch: Partial<SocketState>) {
    const next = { ...this.state, ...patch }
    if (next.connected === this.state.connected && next.degraded === this.state.degraded) return
    this.state = next
    this.stateListeners.forEach((listener) => listener())
  }

  private notify(notice: SocketNotice) {
    this.listeners.forEach((listener) => listener(notice))
  }

  private emitWithAck(event: 'subscribe_instance' | 'join_conversation', data: Record<string, string>) {
    this.socket?.emit(event, data, (response?: AckResponse) => {
      if (!response?.ok) this.notify({ type: 'denied', action: event })
    })
  }

  /**
   * Abre o socket (ou retoma o que foi desligado). Autentica pelo cookie de sessão no handshake
   * (`withCredentials`); o token não passa pelo JavaScript. Chamado só pelo `RealtimeProvider`.
   */
  connect() {
    if (this.socket) {
      if (!this.socket.active) this.socket.connect()
      return
    }
    this.socket = io(SOCKET_URL, {
      withCredentials: true,
      path: SOCKET_PATH,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: RECONNECT_DELAY_MS,
      reconnectionDelayMax: RECONNECT_DELAY_MAX_MS,
    })
    this.setupEventListeners(this.socket)
  }

  /** Fecha o socket (sessão encerrada ou layout desmontado). O interesse das telas fica guardado para o próximo `connect`. */
  disconnect() {
    this.socket?.disconnect()
    this.hasConnected = false
    this.setState({ connected: false, degraded: false })
    this.notify({ type: 'connection', connected: false })
  }

  private resubscribe() {
    this.instances.forEach((_, instanceId) => this.emitWithAck('subscribe_instance', { instanceId }))
    this.conversations.forEach((_, key) => {
      const [instanceId, conversationId] = key.split(':')
      this.emitWithAck('join_conversation', { instanceId, conversationId })
    })
  }

  private setupEventListeners(socket: Socket) {
    socket.on('connect', () => {
      const reconnected = this.hasConnected
      this.hasConnected = true
      this.setState({ connected: true, degraded: false })
      this.notify({ type: 'connection', connected: true })
      this.resubscribe()
      if (reconnected) {
        // O que mudou durante a queda não chegou por evento: refaz o que está em cache e o que o chat tem na tela.
        const client = getQueryClient()
        void client.invalidateQueries({ queryKey: queryKeys.instances })
        void client.invalidateQueries({ queryKey: queryKeys.dashboard })
        this.notify({ type: 'reconnected' })
      }
    })

    socket.on('disconnect', (reason) => {
      // Desligado por nós (logout, layout fechado): não é falha. Qualquer outro motivo o Socket.IO reconecta sozinho.
      const byUs = reason === 'io client disconnect'
      this.setState({ connected: false, degraded: !byUs })
      this.notify({ type: 'connection', connected: false })
    })

    socket.on('connect_error', (error: Error) => {
      // Sessão recusada: reconectar não adianta, encerra pelo caminho do logout. Qualquer outro erro (backend
      // fora, rede) é passageiro: o Socket.IO segue tentando e a UI só avisa.
      if (error.message === UNAUTHORIZED) {
        this.socket?.disconnect()
        endSession()
        return
      }
      this.setState({ connected: false, degraded: true })
    })

    socket.on('new_message', (raw: RealtimeMessage) => {
      const conversation = findConversation(raw.conversation_id)
      if (!conversation) {
        this.notify({ type: 'unknown_conversation' })
        return
      }
      useChatStore.getState().addMessage(mapRealtimeMessage(raw, conversation.id))
    })

    socket.on('conversation_updated', (raw: RealtimeConversation) => {
      const conversation = findConversation(raw.conversation_id)
      if (!conversation) {
        this.notify({ type: 'unknown_conversation' })
        return
      }
      const at = parseServerDate(raw.timestamp)
      useChatStore.getState().upsertConversation({
        ...conversation,
        name: raw.contact_name || conversation.name,
        avatar: raw.avatar || conversation.avatar,
        lastMessage: raw.last_message ?? conversation.lastMessage,
        timestamp: formatTimestamp(at),
        lastMessageAt: at.toISOString(),
        // A Conversation que o usuário abriu já está lida: o backend só soma `unread_count`, a UI zera.
        // A primeira da lista, aberta sozinha, continua não lida.
        unreadCount: isOpenByUser(conversation.id) ? 0 : (raw.unread_count ?? conversation.unreadCount),
      })
      this.notify({ type: 'conversation_activity', conversationId: conversation.id })
    })

    socket.on('message_status_update', ({ message_id, status }: { message_id: string; status: string }) => {
      useChatStore.getState().updateMessageStatus(message_id, mapMessageStatus(status))
    })

    socket.on('connection_status_update', (payload: { status?: string; evolution_state?: string }) => {
      this.notify({
        type: 'instance_status',
        status: normalizeInstanceStatus(payload.evolution_state ?? payload.status),
      })
    })

    socket.on('qr_code_update', (payload: { qrcode?: unknown }) => {
      const qrCode = extractQrCode(payload)
      if (qrCode) this.notify({ type: 'qr_code', qrCode })
    })

    socket.on('human_handoff_requested', (payload: HandoffPayload) => {
      const conversation = findConversation(payload.conversation_id)
      if (conversation) useChatStore.getState().setConversationHandoff(conversation.id, true)
    })

    // Assumir, devolver ou timeout: chega a todas as abas abertas da Instance.
    socket.on('handoff_updated', (payload: HandoffPayload) => {
      const conversation = findConversation(payload.conversation_id)
      if (conversation) {
        useChatStore
          .getState()
          .setConversationHandoff(conversation.id, payload.human_in_loop ?? false, payload.assigned_to ?? null)
      }
    })

    socket.on('thinking_event', (payload: ThinkingPayload) => {
      const conversationId = findConversation(payload.conversation_id)?.id ?? payload.conversation_id
      const store = useChatStore.getState()

      switch (payload.event) {
        case 'thinking_start':
          // Rodada nova: o timer da anterior não pode apagar o Thinking que acabou de começar.
          cancelThinkingClear(conversationId)
          store.setThinkingState(conversationId, 'indicator')
          break
        case 'thinking_end':
          store.collapseThinking(conversationId, payload.data?.summary)
          scheduleThinkingClear(conversationId, () => useChatStore.getState().clearThinking(conversationId))
          break
      }
    })
  }

  subscribeToInstance(instanceId: string) {
    if (count(this.instances, instanceId, 1) === 1 && this.socket?.connected) {
      this.emitWithAck('subscribe_instance', { instanceId })
    }
  }

  leaveInstance(instanceId: string) {
    if (!this.instances.has(instanceId)) return
    if (count(this.instances, instanceId, -1) === 0) this.socket?.emit('leave_instance', { instanceId })
  }

  joinConversation(instanceId: string, conversationId: string) {
    if (count(this.conversations, joinKey(instanceId, conversationId), 1) === 1 && this.socket?.connected) {
      this.emitWithAck('join_conversation', { instanceId, conversationId })
    }
  }

  leaveConversation(instanceId: string, conversationId: string) {
    const key = joinKey(instanceId, conversationId)
    if (!this.conversations.has(key)) return
    if (count(this.conversations, key, -1) === 0) this.socket?.emit('leave_conversation', { instanceId, conversationId })
  }
}

export const socketService = new SocketService()
