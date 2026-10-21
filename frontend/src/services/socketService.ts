import { io, Socket } from 'socket.io-client'
import { WS_URL, API_BASE_URL } from '@/lib/constants'
import { formatTimestamp } from '@/lib/utils'
import { useChatStore } from '@/stores/useChatStore'
import type { Message, Conversation } from '@/types/chat'

const SOCKET_IO_ENABLED = true
const SOCKET_PATH = '/realtime/socket.io'
const NORMALIZED_WS_URL = WS_URL.replace(/^ws/i, 'http')

type ThinkingPayload = {
  conversationId?: string
  conversation_id?: string
  event: string
  data?: Record<string, unknown>
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

  async connect(token?: string) {
    if (!SOCKET_IO_ENABLED) {
      console.log('[Socket] Socket.io connection disabled')
      this.isConnected = false
      return
    }

    if (!token) {
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

    if (this.socket?.connected) {
      return
    }

    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }

    this.socket = io(NORMALIZED_WS_URL, {
      auth: { token },
      path: SOCKET_PATH,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    })

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
    })

    socket.on('disconnect', (reason) => {
      console.log('[Socket] Disconnected:', reason)
      this.isConnected = false
      this.startPolling()
    })

    socket.on('connect_error', (error) => {
      console.error('[Socket] Connection error:', error.message)
      this.reconnectAttempts++

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
