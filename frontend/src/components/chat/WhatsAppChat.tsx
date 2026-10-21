'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { useChatStore } from '@/stores/useChatStore'
import { agentService } from '@/services/agentService'
import { chatService } from '@/services/chatService'
import { socketService } from '@/services/socketService'
import { evolutionSocketService } from '@/services/evolutionSocketService'
import { instanceService } from '@/services/instanceService'
import { useAuthStore } from '@/stores/useAuthStore'
import { useResolvedInstance } from '@/hooks/useResolvedInstance'
import { ChatSidebar } from './ChatSidebar'
import { ChatHeader } from './ChatHeader'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { EmptyChat } from './EmptyChat'
import { TypingIndicator } from './TypingIndicator'
import { ThinkingManager } from './ThinkingManager'
import { SystemMessage } from './SystemMessage'
import { POLLING_INTERVAL, TYPING_TIMEOUT } from '@/lib/constants'
import { generateTempId, formatTimestamp } from '@/lib/utils'
import type { AgentListItem, Message } from '@/types/chat'

const NO_MESSAGES: Message[] = []
const NO_AGENTS: AgentListItem[] = []

export function WhatsAppChat() {
  const {
    conversations,
    messages,
    activeConversationId,
    typingIndicators,
    isLoadingConversations,
    isLoadingMessages,
    isSending,
    setConversations,
    setMessages,
    addMessage,
    updateMessage,
    updateMessageStatus,
    setActiveConversation,
    setLoadingConversations,
    setLoadingMessages,
    setSending,
    setError,
    updateConversationLastMessage,
    resetUnreadCount,
  } = useChatStore()

  const { token } = useAuthStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const { resolvedInstance, isResolvingInstance } = useResolvedInstance()
  const [agentEnabled, setAgentEnabled] = useState<boolean | null>(null)
  const [fetchedAgents, setFetchedAgents] = useState<AgentListItem[]>([])
  const availableAgents = token ? fetchedAgents : NO_AGENTS
  // O vínculo guarda o token com que foi lido; sem token, ou com outro token, ele some no render.
  const [agentBinding, setAgentBinding] = useState<{ token: string | null; id: string | null; name: string | null }>({
    token: null,
    id: null,
    name: null,
  })
  const hasCurrentBinding = token !== null && agentBinding.token === token
  const selectedAgentId = hasCurrentBinding ? agentBinding.id : null
  const selectedAgentName = hasCurrentBinding ? agentBinding.name : null
  const [isAgentStatusLoading, setIsAgentStatusLoading] = useState(false)
  const [isAgentsLoading, setIsAgentsLoading] = useState(false)
  const [isBindingAgent, setIsBindingAgent] = useState(false)
  const [isTogglingAgent, setIsTogglingAgent] = useState(false)
  const [agentStatusError, setAgentStatusError] = useState<string | null>(null)
  const instanceName = resolvedInstance?.instanceName

  const activeConversation = conversations.find((c) => c.id === activeConversationId)
  const activeMessages = (activeConversationId && messages[activeConversationId]) || NO_MESSAGES
  const isTyping = activeConversationId ? typingIndicators[activeConversationId] || false : false

  useEffect(() => {
    if (!token) return

    const loadAvailableAgents = async () => {
      setIsAgentsLoading(true)

      try {
        const response = await agentService.getAgents()
        setFetchedAgents(response.items)
      } catch (error) {
        console.error('Failed to load available agents:', error)
        setAgentStatusError('Nao foi possivel carregar a lista de agentes disponiveis.')
      } finally {
        setIsAgentsLoading(false)
      }
    }

    void loadAvailableAgents()
  }, [token])

  // Scroll to bottom when new messages arrive
  const scrollToBottom = useCallback((instant = false) => {
    messagesEndRef.current?.scrollIntoView({ 
      behavior: instant ? 'auto' : 'smooth' 
    })
  }, [])

  // Rola instantaneamente na primeira carga de cada conversa e suavemente nas seguintes
  const scrolledConversationRef = useRef<string | null>(null)
  useEffect(() => {
    if (activeMessages.length === 0) return
    scrollToBottom(scrolledConversationRef.current !== activeConversationId)
    scrolledConversationRef.current = activeConversationId
  }, [activeMessages, activeConversationId, scrollToBottom])

  // Load agent status on mount
  useEffect(() => {
    if (!instanceName) return

    const loadAgentStatus = async () => {
      setIsAgentStatusLoading(true)
      setAgentStatusError(null)
      setAgentEnabled(null)

      try {
        const status = await instanceService.getAgentStatus(instanceName)
        setAgentEnabled(status.agent_enabled)
        setAgentBinding({ token, id: status.agent_id, name: status.agent_name ?? null })
      } catch (error) {
        console.error('Failed to load agent status:', error)
        const message =
          error instanceof Error
            ? error.message
            : 'Nao foi possivel carregar o status do agente para esta instancia.'
        setAgentStatusError(message)
      } finally {
        setIsAgentStatusLoading(false)
      }
    }

    void loadAgentStatus()
  }, [instanceName, token])

  // Handle agent toggle
  const handleToggleAgent = useCallback(async () => {
    if (!instanceName || agentEnabled === null || isTogglingAgent) return

    if (!agentEnabled && !selectedAgentId) {
      setAgentStatusError('Selecione um agente antes de ativar as respostas automáticas.')
      return
    }

    setAgentStatusError(null)
    setIsTogglingAgent(true)

    try {
      const response = await instanceService.updateAgentStatus(instanceName, !agentEnabled)
      setAgentEnabled(response.agent_enabled)
    } catch (error) {
      console.error('Failed to toggle agent:', error)
      const message =
        error instanceof Error
          ? error.message
          : 'Nao foi possivel atualizar o status do agente. Tente novamente.'
      setAgentStatusError(message)
    } finally {
      setIsTogglingAgent(false)
    }
  }, [instanceName, agentEnabled, selectedAgentId, isTogglingAgent])

  const handleSelectAgent = useCallback(
    async (nextAgentId: string | null) => {
      if (!instanceName || isBindingAgent || nextAgentId === selectedAgentId) return

      setAgentStatusError(null)
      setIsBindingAgent(true)

      try {
        const response = await instanceService.updateAgentBinding(instanceName, nextAgentId)
        setAgentBinding({
          token,
          id: response.agent_id,
          name: response.agent_name ?? availableAgents.find((agent) => agent.id === response.agent_id)?.name ?? null,
        })
        setAgentEnabled(response.agent_enabled)
      } catch (error) {
        console.error('Failed to bind agent:', error)
        const message =
          error instanceof Error
            ? error.message
            : 'Nao foi possivel atualizar o agente vinculado. Tente novamente.'
        setAgentStatusError(message)
      } finally {
        setIsBindingAgent(false)
      }
    },
    [instanceName, isBindingAgent, selectedAgentId, availableAgents, token]
  )

  // Initialize Evolution API WebSocket connection (real-time WhatsApp events)
  useEffect(() => {
    evolutionSocketService.connect()

    const checkConnection = setInterval(() => {
      setIsConnected(evolutionSocketService.getConnectionStatus())
    }, 1000)

    return () => {
      clearInterval(checkConnection)
      evolutionSocketService.disconnect()
    }
  }, [])

  // Subscribe to Evolution API instance for real-time events
  useEffect(() => {
    if (!instanceName) return

    // Enable WebSocket events for this instance on the Evolution API
    void instanceService.enableWebSocket(instanceName)
    evolutionSocketService.subscribeToInstance(instanceName)

    return () => {
      evolutionSocketService.leaveInstance(instanceName)
    }
  }, [instanceName])

  // Initialize backend Socket.IO for agent features (thinking, tool events)
  useEffect(() => {
    if (!token) {
      socketService.disconnect()
      return
    }

    socketService.connect(token)

    return () => {
      socketService.disconnect()
    }
  }, [token])

  useEffect(() => {
    if (!instanceName) return

    socketService.subscribeToInstance(instanceName)

    return () => {
      socketService.leaveInstance(instanceName)
    }
  }, [instanceName])

  // Load conversations on mount (filtered by instance)
  useEffect(() => {
    if (!resolvedInstance) return

    const loadConversations = async () => {
      setLoadingConversations(true)
      try {
        const response = await chatService.getConversations(resolvedInstance.instanceName)
        setConversations(response.items)
      } catch (error) {
        console.error('Failed to load conversations:', error)
        setError('Nao foi possivel carregar os contatos do WhatsApp')
      } finally {
        setLoadingConversations(false)
      }
    }

    loadConversations()

    // Set up polling for conversations as fallback
    pollingRef.current = setInterval(async () => {
      if (!isConnected) {
        try {
          const response = await chatService.getConversations(resolvedInstance.instanceName)
          setConversations(response.items)
        } catch (error) {
          console.error('Polling error:', error)
        }
      }
    }, POLLING_INTERVAL)

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [resolvedInstance, setConversations, setLoadingConversations, setError, isConnected])

  useEffect(() => {
    if (conversations.length === 0) {
      if (activeConversationId) {
        setActiveConversation(null)
      }
      return
    }

    const activeConversationExists = conversations.some(
      (conversation) => conversation.id === activeConversationId
    )

    if (!activeConversationExists) {
      setActiveConversation(conversations[0].id)
    }
  }, [conversations, activeConversationId, setActiveConversation])

  // Load messages when conversation is selected
  useEffect(() => {
    if (!instanceName || !activeConversationId) return

    const loadMessages = async () => {
      setLoadingMessages(true)
      try {
        const response = await chatService.getMessages(instanceName, activeConversationId)
        setMessages(activeConversationId, response.items)
        resetUnreadCount(activeConversationId)
        socketService.joinConversation(activeConversationId)
      } catch (error) {
        console.error('Failed to load messages:', error)
        setError('Nao foi possivel carregar as mensagens desse contato')
      } finally {
        setLoadingMessages(false)
      }
    }

    loadMessages()

    return () => {
      if (activeConversationId) {
        socketService.leaveConversation(activeConversationId)
      }
    }
  }, [
    activeConversationId,
    instanceName,
    setMessages,
    setLoadingMessages,
    setError,
    resetUnreadCount,
  ])

  // Polling for messages when not connected via WebSocket
  useEffect(() => {
    if (!instanceName || !activeConversationId || isConnected) return

    const messagePolling = setInterval(async () => {
      try {
        const response = await chatService.getMessages(instanceName, activeConversationId)
        setMessages(activeConversationId, response.items)
      } catch (error) {
        console.error('Message polling error:', error)
      }
    }, POLLING_INTERVAL)

    return () => clearInterval(messagePolling)
  }, [activeConversationId, instanceName, isConnected, setMessages])

  // Handle conversation selection
  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversation(id)
  }, [setActiveConversation])

  // Handle sending messages
  const handleSendMessage = useCallback(async (content: string) => {
    if (!instanceName || !activeConversationId || isSending) return

    const tempId = generateTempId()
    const tempMessage: Message = {
      id: tempId,
      conversationId: activeConversationId,
      content,
      timestamp: new Date(),
      isOutgoing: true,
      status: 'sending',
      messageType: 'text',
    }

    // Optimistically add message
    addMessage(tempMessage)
    setSending(true)

    try {
      const response = await chatService.sendMessage(instanceName, activeConversationId, content)

      // Update temp message with real message data
      const sentMessage: Message = {
        id: response.message_id || tempId,
        conversationId: activeConversationId,
        content,
        timestamp: new Date(),
        isOutgoing: true,
        status: 'sent',
        messageType: 'text',
      }
      updateMessage(tempId, sentMessage)
      updateConversationLastMessage(
        activeConversationId,
        content,
        formatTimestamp(new Date())
      )
    } catch (error) {
      console.error('Failed to send message:', error)
      updateMessageStatus(tempId, 'pending')
      setError('Nao foi possivel enviar a mensagem')
    } finally {
      setSending(false)
    }
  }, [
    instanceName,
    activeConversationId,
    isSending,
    addMessage,
    updateMessage,
    updateMessageStatus,
    setSending,
    setError,
    updateConversationLastMessage,
  ])

  // Handle typing indicator
  const handleTyping = useCallback(() => {
    if (!activeConversationId) return

    socketService.sendTypingIndicator(activeConversationId, true)

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current)
    }

    typingTimeoutRef.current = setTimeout(() => {
      if (activeConversationId) {
        socketService.sendTypingIndicator(activeConversationId, false)
      }
    }, TYPING_TIMEOUT)
  }, [activeConversationId])

  // Cleanup typing timeout
  useEffect(() => {
    return () => {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current)
      }
    }
  }, [])

  if (isResolvingInstance && !resolvedInstance) {
    return (
      <div className="flex flex-1 h-full min-h-0 items-center justify-center bg-brand-base text-content-muted">
        Carregando instância...
      </div>
    )
  }

  return (
    <div className="flex flex-1 h-full min-h-0 bg-brand-base overflow-hidden">
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        isLoading={isLoadingConversations}
      />
      <div className="flex-1 flex flex-col min-h-0 relative overflow-hidden">
        {/* Chat Layer Background */}
        <div className="absolute inset-0 chat-pattern opacity-80 pointer-events-none z-0" />

        <div className="relative z-10 flex flex-col h-full">
          {activeConversation ? (
            <>
              <ChatHeader
                name={activeConversation.name}
                avatar={activeConversation.avatar}
                status={isTyping ? 'digitando...' : (activeConversation.isOnline ? 'Online' : 'Offline')}
                isOnline={activeConversation.isOnline}
                agentEnabled={agentEnabled}
                agentName={selectedAgentName}
                availableAgents={availableAgents}
                selectedAgentId={selectedAgentId}
                onSelectAgent={handleSelectAgent}
                onToggleAgent={handleToggleAgent}
                isAgentLoading={isAgentStatusLoading || isTogglingAgent}
                isAgentBindingLoading={isAgentsLoading || isBindingAgent}
              />
              {agentStatusError && (
                <div className="border-b border-warning/20 bg-warning/10 px-6 py-3 text-sm text-warning">
                  {agentStatusError}
                </div>
              )}
              <div className="flex-1 overflow-y-auto px-6 py-8 h-full relative">
                {isLoadingMessages ? (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                  </div>
                ) : (
                  <div className="space-y-6">
                    {activeMessages.map((message) => {
                      if (message.messageType === 'system' && message.systemMetadata) {
                        return <SystemMessage key={message.id} metadata={message.systemMetadata} />
                      }
                      return <MessageBubble key={message.id} message={message} />
                    })}
                    {activeConversationId && <ThinkingManager conversationId={activeConversationId} />}
                    {isTyping && <TypingIndicator />}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>
              <ChatInput
                onSendMessage={handleSendMessage}
                onTyping={handleTyping}
                disabled={isSending}
              />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <EmptyChat />
            </div>
          )}
        </div>
      </div>
      {/* Connection status indicator */}
      {!isConnected && (
        <div className="fixed bottom-4 right-4 rounded-lg bg-brand-card/90 border border-brand-border px-4 py-2 text-sm text-content-muted backdrop-blur-sm">
          <span className="inline-block w-2 h-2 rounded-full bg-yellow-500 mr-2 animate-pulse" />
          Conectando ao WhatsApp...
        </div>
      )}
    </div>
  )
}
