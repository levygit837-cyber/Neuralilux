'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useChatStore } from '@/stores/useChatStore'
import { agentService } from '@/services/agentService'
import { chatService } from '@/services/chatService'
import { socketService } from '@/services/socketService'
import { instanceService, EvolutionInstance } from '@/services/instanceService'
import { useAuthStore } from '@/stores/useAuthStore'
import { useInstanceStore, SelectedInstance } from '@/stores/useInstanceStore'
import { ChatSidebar } from './ChatSidebar'
import { ChatHeader } from './ChatHeader'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { EmptyChat } from './EmptyChat'
import { TypingIndicator } from './TypingIndicator'
import { ThinkingManager } from './ThinkingManager'
import { POLLING_INTERVAL, TYPING_TIMEOUT, ROUTES } from '@/lib/constants'
import { generateTempId, formatTimestamp } from '@/lib/utils'
import type { Message } from '@/types/chat'
import type { AgentListItem } from '@/types/agent'

export function WhatsAppChat() {
  const router = useRouter()
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
  const { selectedInstance, setSelectedInstance } = useInstanceStore()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isInitialLoad, setIsInitialLoad] = useState(true)
  const [resolvedInstance, setResolvedInstance] = useState<SelectedInstance | null>(
    selectedInstance
  )
  const [isResolvingInstance, setIsResolvingInstance] = useState(true)
  const [agentEnabled, setAgentEnabled] = useState<boolean | null>(null)
  const [availableAgents, setAvailableAgents] = useState<AgentListItem[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [selectedAgentName, setSelectedAgentName] = useState<string | null>(null)
  const [isAgentStatusLoading, setIsAgentStatusLoading] = useState(false)
  const [isAgentsLoading, setIsAgentsLoading] = useState(false)
  const [isBindingAgent, setIsBindingAgent] = useState(false)
  const [isTogglingAgent, setIsTogglingAgent] = useState(false)
  const [agentStatusError, setAgentStatusError] = useState<string | null>(null)
  const instanceName = resolvedInstance?.instanceName

  const activeConversation = conversations.find((c) => c.id === activeConversationId)
  const activeMessages = activeConversationId ? messages[activeConversationId] || [] : []
  const isTyping = activeConversationId ? typingIndicators[activeConversationId] || false : false

  const mapToSelectedInstance = useCallback((instance: EvolutionInstance): SelectedInstance => ({
    instanceName: instance.instance.instanceName,
    instanceId: instance.instance.instanceId,
    status: instance.instance.state || instance.socket?.state || 'close',
  }), [])

  const resolveInstance = useCallback(async () => {
    setIsResolvingInstance(true)

    try {
      const instances = await instanceService.fetchInstances()
      const availableInstances = instances.map(mapToSelectedInstance)

      if (availableInstances.length === 0) {
        setResolvedInstance(null)
        return
      }

      const normalizedSelectedName = selectedInstance?.instanceName?.toLowerCase()
      const matchingInstance =
        availableInstances.find(
          (instance) =>
            instance.instanceId === selectedInstance?.instanceId ||
            instance.instanceName.toLowerCase() === normalizedSelectedName
        ) ||
        availableInstances.find((instance) => instance.status === 'open') ||
        availableInstances[0]

      setResolvedInstance(matchingInstance)

      if (
        !selectedInstance ||
        matchingInstance.instanceId !== selectedInstance.instanceId ||
        matchingInstance.instanceName !== selectedInstance.instanceName ||
        matchingInstance.status !== selectedInstance.status
      ) {
        setSelectedInstance(matchingInstance)
      }
    } catch (error) {
      console.error('Failed to resolve active instance:', error)
      setResolvedInstance(selectedInstance ?? null)
    } finally {
      setIsResolvingInstance(false)
    }
  }, [mapToSelectedInstance, selectedInstance, setSelectedInstance])

  useEffect(() => {
    void resolveInstance()
  }, [resolveInstance])

  useEffect(() => {
    if (!isResolvingInstance && !resolvedInstance) {
      router.push(ROUTES.HOME)
    }
  }, [isResolvingInstance, resolvedInstance, router])

  useEffect(() => {
    if (!token) {
      setAvailableAgents([])
      setSelectedAgentId(null)
      setSelectedAgentName(null)
      return
    }

    const loadAvailableAgents = async () => {
      setIsAgentsLoading(true)

      try {
        const response = await agentService.getAgents()
        setAvailableAgents(response.items)
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

  useEffect(() => {
    if (activeMessages.length > 0) {
      scrollToBottom(isInitialLoad)
      if (isInitialLoad) {
        setIsInitialLoad(false)
      }
    }
  }, [activeMessages, scrollToBottom, isInitialLoad])

  // Reset initial load flag when conversation changes
  useEffect(() => {
    setIsInitialLoad(true)
  }, [activeConversationId])

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
        setSelectedAgentId(status.agent_id)
        setSelectedAgentName(status.agent_name ?? null)
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
  }, [instanceName])

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
        setSelectedAgentId(response.agent_id)
        setSelectedAgentName(
          response.agent_name ?? availableAgents.find((agent) => agent.id === response.agent_id)?.name ?? null
        )
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
    [instanceName, isBindingAgent, selectedAgentId, availableAgents]
  )

  // Initialize WebSocket connection
  useEffect(() => {
    if (!token) {
      setIsConnected(false)
      socketService.disconnect()
      return
    }

    socketService.connect(token)

    const checkConnection = setInterval(() => {
      setIsConnected(socketService.getConnectionStatus())
    }, 1000)

    return () => {
      clearInterval(checkConnection)
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
    isConnected,
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
      <div className="flex h-full min-h-0 items-center justify-center bg-dark text-text-gray">
        Carregando instância...
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 bg-dark">
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        isLoading={isLoadingConversations}
      />
      <div className="flex min-h-0 flex-1 flex-col">
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
              <div className="border-b border-yellow-500/20 bg-yellow-500/10 px-6 py-3 text-sm text-yellow-300">
                {agentStatusError}
              </div>
            )}
            <div className="flex-1 overflow-y-auto p-6">
              {isLoadingMessages ? (
                <div className="flex h-full items-center justify-center">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                </div>
              ) : (
                <div className="space-y-4">
                  {activeMessages.map((message) => (
                    <MessageBubble key={message.id} message={message} />
                  ))}
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
          <EmptyChat />
        )}
      </div>
      {/* Connection status indicator */}
      {!isConnected && (
        <div className="fixed bottom-4 right-4 rounded-lg bg-yellow-500/20 px-4 py-2 text-sm text-yellow-400">
          Modo offline - usando polling
        </div>
      )}
    </div>
  )
}
