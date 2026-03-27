'use client'

import { useEffect, useCallback, useRef, useState } from 'react'
import { useChatStore } from '@/stores/useChatStore'
import { chatService } from '@/services/chatService'
import { socketService } from '@/services/socketService'
import { useAuthStore } from '@/stores/useAuthStore'
import { ChatSidebar } from './ChatSidebar'
import { ChatHeader } from './ChatHeader'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { EmptyChat } from './EmptyChat'
import { TypingIndicator } from './TypingIndicator'
import { POLLING_INTERVAL, TYPING_TIMEOUT } from '@/lib/constants'
import { generateTempId, formatTimestamp } from '@/lib/utils'
import type { Message } from '@/types/chat'

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

  const activeConversation = conversations.find((c) => c.id === activeConversationId)
  const activeMessages = activeConversationId ? messages[activeConversationId] || [] : []
  const isTyping = activeConversationId ? typingIndicators[activeConversationId] || false : false

  // Scroll to bottom when new messages arrive
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [activeMessages, scrollToBottom])

  // Initialize WebSocket connection
  useEffect(() => {
    socketService.connect(token ?? undefined)

    const checkConnection = setInterval(() => {
      setIsConnected(socketService.getConnectionStatus())
    }, 1000)

    return () => {
      clearInterval(checkConnection)
      socketService.disconnect()
    }
  }, [token])

  // Load conversations on mount
  useEffect(() => {
    const loadConversations = async () => {
      setLoadingConversations(true)
      try {
        const data = await chatService.getConversations()
        setConversations(data)
      } catch (error) {
        console.error('Failed to load conversations:', error)
        setError('Failed to load conversations')
      } finally {
        setLoadingConversations(false)
      }
    }

    loadConversations()

    // Set up polling for conversations as fallback
    pollingRef.current = setInterval(async () => {
      if (!isConnected) {
        try {
          const data = await chatService.getConversations()
          setConversations(data)
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
  }, [setConversations, setLoadingConversations, setError, isConnected])

  // Load messages when conversation is selected
  useEffect(() => {
    if (!activeConversationId) return

    const loadMessages = async () => {
      setLoadingMessages(true)
      try {
        const data = await chatService.getMessages(activeConversationId)
        setMessages(activeConversationId, data)
        resetUnreadCount(activeConversationId)
        socketService.joinConversation(activeConversationId)
      } catch (error) {
        console.error('Failed to load messages:', error)
        setError('Failed to load messages')
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
  }, [activeConversationId, setMessages, setLoadingMessages, setError, resetUnreadCount])

  // Polling for messages when not connected via WebSocket
  useEffect(() => {
    if (!activeConversationId || isConnected) return

    const messagePolling = setInterval(async () => {
      try {
        const data = await chatService.getMessages(activeConversationId)
        setMessages(activeConversationId, data)
      } catch (error) {
        console.error('Message polling error:', error)
      }
    }, POLLING_INTERVAL)

    return () => clearInterval(messagePolling)
  }, [activeConversationId, isConnected, setMessages])

  // Handle conversation selection
  const handleSelectConversation = useCallback((id: string) => {
    setActiveConversation(id)
  }, [setActiveConversation])

  // Handle sending messages
  const handleSendMessage = useCallback(async (content: string) => {
    if (!activeConversationId || isSending) return

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
      // Send via WebSocket if connected
      if (isConnected) {
        socketService.sendMessage(activeConversationId, content, tempId)
      }

      // Always send via HTTP as backup/confirmation
      const sentMessage = await chatService.sendMessage(activeConversationId, content)
      
      // Update temp message with real message data
      updateMessage(tempId, sentMessage)
      updateConversationLastMessage(
        activeConversationId,
        content,
        formatTimestamp(new Date())
      )
    } catch (error) {
      console.error('Failed to send message:', error)
      updateMessageStatus(tempId, 'pending')
      setError('Failed to send message')
    } finally {
      setSending(false)
    }
  }, [activeConversationId, isSending, isConnected, addMessage, updateMessage, updateMessageStatus, setSending, setError, updateConversationLastMessage])

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

  return (
    <div className="flex h-screen bg-dark">
      <ChatSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        isLoading={isLoadingConversations}
      />
      <div className="flex flex-1 flex-col">
        {activeConversation ? (
          <>
            <ChatHeader
              name={activeConversation.name}
              avatar={activeConversation.avatar}
              status={isTyping ? 'digitando...' : (activeConversation.isOnline ? 'Online' : 'Offline')}
              isOnline={activeConversation.isOnline}
            />
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