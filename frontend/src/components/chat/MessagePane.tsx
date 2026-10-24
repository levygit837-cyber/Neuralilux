'use client'

import { useEffect, useRef } from 'react'
import { selectActiveConversation, useChatStore } from '@/stores/useChatStore'
import { MessageBubble } from './MessageBubble'
import { ChatInput } from './ChatInput'
import { TypingIndicator } from './TypingIndicator'
import { ThinkingManager } from './ThinkingManager'
import { SystemMessage } from './SystemMessage'
import type { Message } from '@/types/chat'

const NO_MESSAGES: Message[] = []

interface MessagePaneProps {
  conversationId: string
  onSendMessage: (content: string) => void
  onRetryMessage: (messageId: string) => void
}

/** Messages da Conversation aberta, o indicador de pensamento do Agent e o campo de envio. */
export function MessagePane({ conversationId, onSendMessage, onRetryMessage }: MessagePaneProps) {
  const messages = useChatStore((state) => state.messages[conversationId]) ?? NO_MESSAGES
  const isTyping = useChatStore((state) => state.typingIndicators[conversationId] ?? false)
  const isLoading = useChatStore((state) => state.isLoadingMessages)
  const isSending = useChatStore((state) => state.isSending)
  const isGroup = useChatStore((state) => selectActiveConversation(state)?.isGroup ?? false)
  const endRef = useRef<HTMLDivElement>(null)
  const scrolledRef = useRef<string | null>(null)

  // Primeira carga de cada conversa rola de uma vez; as seguintes, suavemente.
  useEffect(() => {
    if (messages.length === 0) return
    endRef.current?.scrollIntoView({ behavior: scrolledRef.current === conversationId ? 'smooth' : 'auto' })
    scrolledRef.current = conversationId
  }, [messages, conversationId])

  return (
    <>
      <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-8 h-full relative">
        {isLoading && messages.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((message) =>
              message.messageType === 'system' && message.systemMetadata ? (
                <SystemMessage key={message.id} metadata={message.systemMetadata} />
              ) : (
                <MessageBubble key={message.id} message={message} showSender={isGroup} onRetry={onRetryMessage} />
              )
            )}
            <ThinkingManager conversationId={conversationId} />
            {isTyping && <TypingIndicator />}
            <div ref={endRef} />
          </div>
        )}
      </div>
      <ChatInput onSendMessage={onSendMessage} disabled={isSending} />
    </>
  )
}
