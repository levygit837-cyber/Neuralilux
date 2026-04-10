import { io, Socket } from 'socket.io-client'
import { WS_URL, API_BASE_URL } from '@/lib/constants'
import { formatTimestamp } from '@/lib/utils'
import { useChatStore } from '@/stores/useChatStore'
import type { Message, Conversation } from '@/types/chat'

const SOCKET_IO_ENABLED = true
const SOCKET_PATH = '/realtime/socket.io'
const NORMALIZED_WS_URL = WS_URL.replace(/^ws/i, 'http')

type AgentThinkingCallback = (event: string, data?: Record<string, unknown>) => void

type ThinkingPayload = {
  conversationId?: string
  conversation_id?: string
  event: string
  data?: Record<string, unknown>
}

type ToolEventPayload = {
  conversationId?: string
  conversation_id?: string
  sessionId?: string
  session_id?: string
  phase?: 'waiting_input' | 'started' | 'completed' | 'failed'
  source?: string
  traceId?: string
  trace_id?: string
  requestId?: string
  request_id?: string
  toolName?: string
  tool_name?: string
  displayName?: string
  display_name?: string
  inputPreview?: string
  input_preview?: string
  outputPreview?: string
  output_preview?: string
  inputPayload?: Record<string, unknown>
  input_payload?: Record<string, unknown>
  outputPayload?: unknown
  output_payload?: unknown
  error?: string
  startedAt?: string
  started_at?: string
  finishedAt?: string
  finished_at?: string
}

type SocketConnectOptions = {
  allowGuestAgentChat?: boolean
}

class SocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private pollingInterval: NodeJS.Timeout | null = null
  private isConnected = false
  private isServerReachable = false
  private connectivityCheckInterval: NodeJS.Timeout | null = null
  private subscribedInstance: string | null = null
  private clearTimers: Map<string, ReturnType<typeof setTimeout>> = new Map()
  private agentThinkingCallback: AgentThinkingCallback | null = null
  private activeAgentChatSession: string | null = null
  private allowGuestAgentChat = false
  private guestFallbackAttempted = false
  private connectionMode: 'authenticated' | 'guest_agent_chat' | null = null

  private waitForConnection(timeoutMs: number = 5000): Promise<boolean> {
    const socket = this.socket

    if (!socket) {
      return Promise.resolve(false)
    }

    if (socket.connected) {
      return Promise.resolve(true)
    }

    return new Promise((resolve) => {
      let timeoutId: ReturnType<typeof setTimeout> | null = null

      const cleanup = () => {
        if (timeoutId) {
          clearTimeout(timeoutId)
        }
        socket.off('connect', handleConnect)
      }

      const handleConnect = () => {
        cleanup()
        resolve(true)
      }

      timeoutId = setTimeout(() => {
        cleanup()
        resolve(socket.connected)
      }, timeoutMs)

      socket.on('connect', handleConnect)
    })
  }

  private emitWithAck<T>(
    eventName: string,
    payload: Record<string, unknown>,
    timeoutMs: number = 3000
  ): Promise<T | null> {
    const socket = this.socket
    if (!socket?.connected) {
      return Promise.resolve(null)
    }

    return new Promise((resolve) => {
      let settled = false

      const timeoutId = setTimeout(() => {
        if (settled) return
        settled = true
        resolve(null)
      }, timeoutMs)

      socket.emit(eventName, payload, (response: T) => {
        if (settled) return
        settled = true
        clearTimeout(timeoutId)
        resolve(response)
      })
    })
  }

  private async checkServerConnectivity(): Promise<boolean> {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 3000)

      const response = await fetch(`${API_BASE_URL}/health`, {
        method: 'GET',
        signal: controller.signal,
      })

      clearTimeout(timeoutId)
      return response.ok
    } catch {
      return false
    }
  }

  startConnectivityMonitor(intervalMs: number = 10000) {
    if (this.connectivityCheckInterval) return

    void this.checkServerConnectivity().then((reachable) => {
      this.isServerReachable = reachable
    })

    this.connectivityCheckInterval = setInterval(async () => {
      this.isServerReachable = await this.checkServerConnectivity()
    }, intervalMs)
  }

  stopConnectivityMonitor() {
    if (this.connectivityCheckInterval) {
      clearInterval(this.connectivityCheckInterval)
      this.connectivityCheckInterval = null
    }
  }

  private isTokenExpired(token?: string): boolean {
    if (!token) {
      return true
    }

    try {
      const [, payload] = token.split('.')
      if (!payload) {
        return true
      }

      const normalizedPayload = payload.replace(/-/g, '+').replace(/_/g, '/')
      const decodedPayload = JSON.parse(
        atob(normalizedPayload.padEnd(Math.ceil(normalizedPayload.length / 4) * 4, '='))
      )
      const exp = typeof decodedPayload.exp === 'number' ? decodedPayload.exp : 0

      return exp > 0 ? Date.now() >= exp * 1000 : true
    } catch {
      return true
    }
  }

  async connect(token?: string, options: SocketConnectOptions = {}) {
    if (!SOCKET_IO_ENABLED) {
      console.log('[Socket] Socket.io connection disabled')
      this.isConnected = false
      return
    }

    const allowGuestAgentChat = options.allowGuestAgentChat === true
    this.allowGuestAgentChat = allowGuestAgentChat

    const shouldUseGuestAgentChat = allowGuestAgentChat && this.isTokenExpired(token)
    const authToken = shouldUseGuestAgentChat ? undefined : token
    const desiredMode: 'authenticated' | 'guest_agent_chat' = shouldUseGuestAgentChat
      ? 'guest_agent_chat'
      : 'authenticated'

    if (!authToken && !shouldUseGuestAgentChat) {
      console.log('[Socket] Missing auth token, skipping realtime connection')
      this.isConnected = false
      return
    }

    const isReachable = await this.checkServerConnectivity()
    if (!isReachable) {
      console.log('[Socket] Server not reachable - falling back to polling mode')
      this.startPolling()
      return
    }

    if (this.socket?.connected && this.connectionMode === desiredMode) {
      return
    }

    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }

    this.socket = io(NORMALIZED_WS_URL, {
      auth: shouldUseGuestAgentChat ? { guestAgentChat: true } : { token: authToken },
      path: SOCKET_PATH,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    })

    this.connectionMode = desiredMode
    this.guestFallbackAttempted = shouldUseGuestAgentChat
    this.setupEventListeners()
  }

  private setupEventListeners() {
    const socket = this.socket
    if (!socket) return

    socket.on('connect', () => {
      console.log('[Socket] Connected')
      this.isConnected = true
      this.reconnectAttempts = 0
      this.stopPolling()

      if (this.subscribedInstance) {
        socket.emit('subscribe_instance', { instanceName: this.subscribedInstance })
      }

      if (this.activeAgentChatSession) {
        socket.emit('join_agent_chat', { sessionId: this.activeAgentChatSession })
      }
    })

    socket.on('disconnect', (reason) => {
      console.log('[Socket] Disconnected:', reason)
      this.isConnected = false
      this.startPolling()
    })

    socket.on('connect_error', (error) => {
      console.error('[Socket] Connection error:', error.message)
      this.reconnectAttempts++

      if (
        this.allowGuestAgentChat &&
        this.connectionMode === 'authenticated' &&
        !this.guestFallbackAttempted
      ) {
        this.guestFallbackAttempted = true
        this.connectionMode = 'guest_agent_chat'
        socket.disconnect()
        this.socket = null
        void this.connect(undefined, { allowGuestAgentChat: true })
        return
      }

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.log('[Socket] Max reconnection attempts reached, falling back to polling')
        this.startPolling()
      }
    })

    socket.on('new_message', (message: Message & { timestamp: string | Date }) => {
      const { addMessage } = useChatStore.getState()
      addMessage(this.normalizeMessage(message))
    })

    socket.on(
      'message_status_update',
      ({ messageId, status }: { messageId: string; status: Message['status'] }) => {
        const { updateMessageStatus } = useChatStore.getState()
        updateMessageStatus(messageId, status)
      }
    )

    socket.on('typing', ({ conversationId, isTyping }: { conversationId: string; isTyping: boolean }) => {
      const { setTyping } = useChatStore.getState()
      setTyping(conversationId, isTyping)
    })

    socket.on('conversation_updated', (conversation: Conversation) => {
      const { upsertConversation } = useChatStore.getState()
      upsertConversation(this.normalizeConversation(conversation))
    })

    socket.on('connection_status_update', (payload: { status: string; evolutionState: string }) => {
      console.log('[Socket] WhatsApp connection status updated:', payload)
    })

    socket.on('thinking_event', (payload: ThinkingPayload) => {
      const { setThinkingState, appendThinkingToken, collapseThinking, clearThinking } =
        useChatStore.getState()

      const conversationId = payload.conversationId ?? payload.conversation_id
      const event = payload.event
      const data = payload.data

      if (!conversationId) {
        return
      }

      if (this.agentThinkingCallback) {
        this.agentThinkingCallback(event, { ...data, conversationId })
      }

      switch (event) {
        case 'thinking_start':
          setThinkingState(conversationId, 'indicator')
          break
        case 'thinking_token':
          if (typeof data?.token === 'string') {
            appendThinkingToken(conversationId, data.token)
          }
          break
        case 'thinking_end': {
          collapseThinking(conversationId, data?.summary as string | undefined)
          const timer = setTimeout(() => {
            clearThinking(conversationId)
          }, 5000)

          const { thinkingClearTimers } = useChatStore.getState()
          useChatStore.setState({
            thinkingClearTimers: {
              ...thinkingClearTimers,
              [conversationId]: timer,
            },
          })
          break
        }
      }
    })

    socket.on('tool_event', (payload: ToolEventPayload) => {
      const conversationId =
        payload.conversationId ??
        payload.conversation_id ??
        payload.sessionId ??
        payload.session_id

      if (!conversationId || !this.agentThinkingCallback) {
        return
      }

      const phase = payload.phase
      if (!phase) {
        return
      }

      this.agentThinkingCallback(`tool_${phase}`, {
        conversationId,
        sessionId: payload.sessionId ?? payload.session_id ?? conversationId,
        source: payload.source,
        traceId: payload.traceId ?? payload.trace_id,
        requestId: payload.requestId ?? payload.request_id,
        toolName: payload.toolName ?? payload.tool_name,
        displayName: payload.displayName ?? payload.display_name,
        inputPreview: payload.inputPreview ?? payload.input_preview,
        outputPreview: payload.outputPreview ?? payload.output_preview,
        inputPayload: payload.inputPayload ?? payload.input_payload,
        outputPayload: payload.outputPayload ?? payload.output_payload,
        error: payload.error,
        phase,
        startedAt: payload.startedAt ?? payload.started_at,
        finishedAt: payload.finishedAt ?? payload.finished_at,
      })
    })
  }

  async connectForAgentChat(token?: string) {
    await this.connect(token, { allowGuestAgentChat: true })
  }

  async ensureAgentChatReady(sessionId: string, token?: string): Promise<boolean> {
    this.activeAgentChatSession = sessionId
    await this.connectForAgentChat(token)

    const connected = await this.waitForConnection()
    if (!connected) {
      return false
    }

    const response = await this.emitWithAck<{ ok?: boolean }>('join_agent_chat', { sessionId })
    return response?.ok === true
  }

  private startPolling() {
    if (this.pollingInterval) return

    console.log('[Socket] Starting polling fallback')
    this.pollingInterval = setInterval(() => {
      void 0
    }, 3000)
  }

  private stopPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval)
      this.pollingInterval = null
    }
  }

  sendMessage(conversationId: string, content: string, tempId: string) {
    if (this.socket?.connected) {
      this.socket.emit('send_message', {
        instanceName: this.subscribedInstance,
        conversationId,
        content,
        tempId,
      })
    } else {
      console.log('[Socket] Not connected, message will be sent via HTTP')
    }
  }

  sendTypingIndicator(conversationId: string, isTyping: boolean) {
    if (this.socket?.connected) {
      this.socket.emit('typing', { conversationId, isTyping })
    }
  }

  joinConversation(conversationId: string) {
    if (this.socket?.connected && this.subscribedInstance) {
      this.socket.emit('join_conversation', {
        instanceName: this.subscribedInstance,
        conversationId,
      })
    }
  }

  leaveConversation(conversationId: string) {
    if (this.socket?.connected && this.subscribedInstance) {
      this.socket.emit('leave_conversation', {
        instanceName: this.subscribedInstance,
        conversationId,
      })
    }
  }

  subscribeToInstance(instanceName: string) {
    this.subscribedInstance = instanceName

    if (this.socket?.connected) {
      this.socket.emit('subscribe_instance', { instanceName })
    }
  }

  leaveInstance(instanceName: string) {
    if (this.socket?.connected) {
      this.socket.emit('leave_instance', { instanceName })
    }

    if (this.subscribedInstance === instanceName) {
      this.subscribedInstance = null
    }
  }

  async joinAgentChat(sessionId: string): Promise<boolean> {
    this.activeAgentChatSession = sessionId
    if (!this.socket?.connected) {
      return false
    }

    const response = await this.emitWithAck<{ ok?: boolean }>('join_agent_chat', { sessionId })
    console.log('[Socket] Joined agent chat room:', sessionId)
    return response?.ok === true
  }

  leaveAgentChat(sessionId: string) {
    if (this.activeAgentChatSession === sessionId) {
      this.activeAgentChatSession = null
    }

    if (this.socket?.connected) {
      this.socket.emit('leave_agent_chat', { sessionId })
      console.log('[Socket] Left agent chat room:', sessionId)
    }
  }

  setAgentThinkingCallback(callback: AgentThinkingCallback | null) {
    this.agentThinkingCallback = callback
  }

  getConnectionStatus(): boolean {
    return this.isConnected
  }

  getServerReachableStatus(): boolean {
    return this.isServerReachable
  }

  disconnect() {
    this.stopPolling()
    this.stopConnectivityMonitor()
    this.clearTimers.forEach((timer) => clearTimeout(timer))
    this.clearTimers.clear()

    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }

    this.isConnected = false
    this.subscribedInstance = null
    this.activeAgentChatSession = null
    this.allowGuestAgentChat = false
    this.guestFallbackAttempted = false
    this.connectionMode = null
  }

  private normalizeMessage(message: Message & { timestamp: string | Date }): Message {
    return {
      ...message,
      timestamp: message.timestamp instanceof Date ? message.timestamp : new Date(message.timestamp),
    }
  }

  private normalizeConversation(conversation: Conversation): Conversation {
    const rawTimestamp =
      (conversation as Conversation & { last_message_at?: string; updated_at?: string }).timestamp ||
      (conversation as Conversation & { last_message_at?: string; updated_at?: string }).last_message_at ||
      (conversation as Conversation & { last_message_at?: string; updated_at?: string }).updated_at ||
      ''

    return {
      ...conversation,
      timestamp: rawTimestamp ? formatTimestamp(rawTimestamp) : '',
      unreadCount: conversation.unreadCount ?? 0,
    }
  }
}

export const socketService = new SocketService()
