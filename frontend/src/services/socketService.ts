import { io, Socket } from 'socket.io-client'
import { WS_URL, API_BASE_URL } from '@/lib/constants'
import { useChatStore } from '@/stores/useChatStore'
import type { Message } from '@/types/chat'

// Feature flag to enable/disable socket.io connection
// Set to true when backend has socket.io support
const SOCKET_IO_ENABLED = false

class SocketService {
  private socket: Socket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private pollingInterval: NodeJS.Timeout | null = null
  private isConnected = false
  private isServerReachable = false
  private connectivityCheckInterval: NodeJS.Timeout | null = null

  /**
   * Check if the backend server is reachable via HTTP
   * Returns true if server responds, false otherwise
   */
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

  /**
   * Initialize connectivity monitoring
   * Periodically checks if server is reachable
   */
  startConnectivityMonitor(intervalMs: number = 10000) {
    if (this.connectivityCheckInterval) return

    // Initial check
    this.checkServerConnectivity().then(reachable => {
      this.isServerReachable = reachable
    })

    // Periodic checks
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
    // Skip socket.io connection if feature is disabled
    if (!SOCKET_IO_ENABLED) {
      console.log('[Socket] Socket.io connection disabled - using HTTP polling mode')
      this.startConnectivityMonitor()
      this.startPolling()
      return
    }

    // Check server connectivity before attempting socket connection
    const isReachable = await this.checkServerConnectivity()
    if (!isReachable) {
      console.log('[Socket] Server not reachable - falling back to polling mode')
      this.startPolling()
      return
    }

    if (this.socket?.connected) return

    this.socket = io(WS_URL, {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: this.reconnectDelay,
    })

    this.setupEventListeners()
  }

  private setupEventListeners() {
    if (!this.socket) return

    this.socket.on('connect', () => {
      console.log('[Socket] Connected')
      this.isConnected = true
      this.reconnectAttempts = 0
      this.stopPolling()
    })

    this.socket.on('disconnect', (reason) => {
      console.log('[Socket] Disconnected:', reason)
      this.isConnected = false
      this.startPolling()
    })

    this.socket.on('connect_error', (error) => {
      console.error('[Socket] Connection error:', error.message)
      this.reconnectAttempts++
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.log('[Socket] Max reconnection attempts reached, falling back to polling')
        this.startPolling()
      }
    })

    // Listen for new messages
    this.socket.on('new_message', (message: Message) => {
      const { addMessage } = useChatStore.getState()
      addMessage(message)
    })

    // Listen for message status updates
    this.socket.on('message_status_update', ({ messageId, status }: { messageId: string; status: Message['status'] }) => {
      const { updateMessageStatus } = useChatStore.getState()
      updateMessageStatus(messageId, status)
    })

    // Listen for typing indicators
    this.socket.on('typing', ({ conversationId, isTyping }: { conversationId: string; isTyping: boolean }) => {
      const { setTyping } = useChatStore.getState()
      setTyping(conversationId, isTyping)
    })

    // Listen for conversation updates
    this.socket.on('conversation_updated', (conversation: any) => {
      const { conversations, setConversations } = useChatStore.getState()
      const updatedConversations = conversations.map((c) =>
        c.id === conversation.id ? { ...c, ...conversation } : c
      )
      setConversations(updatedConversations)
    })
  }

  // Fallback polling when WebSocket is unavailable
  private startPolling() {
    if (this.pollingInterval) return
    
    console.log('[Socket] Starting polling fallback')
    // Polling will be handled by the chat page component
    // This is just a flag to indicate polling mode
    this.pollingInterval = setInterval(() => {
      // Polling logic is handled by React Query in the components
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
      this.socket.emit('send_message', { conversationId, content, tempId })
    } else {
      // Fallback: message will be sent via HTTP API
      console.log('[Socket] Not connected, message will be sent via HTTP')
    }
  }

  sendTypingIndicator(conversationId: string, isTyping: boolean) {
    if (this.socket?.connected) {
      this.socket.emit('typing', { conversationId, isTyping })
    }
  }

  joinConversation(conversationId: string) {
    if (this.socket?.connected) {
      this.socket.emit('join_conversation', { conversationId })
    }
  }

  leaveConversation(conversationId: string) {
    if (this.socket?.connected) {
      this.socket.emit('leave_conversation', { conversationId })
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
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
    }
    this.isConnected = false
  }
}

export const socketService = new SocketService()
