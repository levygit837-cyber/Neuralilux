'use client'

import { useState } from 'react'
import { ChatSidebar } from '@/components/chat/ChatSidebar'
import { ChatHeader } from '@/components/chat/ChatHeader'
import { MessageBubble } from '@/components/chat/MessageBubble'
import { ChatInput } from '@/components/chat/ChatInput'
import { EmptyChat } from '@/components/chat/EmptyChat'
import { TypingIndicator } from '@/components/chat/TypingIndicator'
import type { Conversation, Message } from '@/types/chat'

// Mock data
const mockConversations: Conversation[] = [
  {
    id: '1',
    name: 'Maria Silva',
    avatar: '',
    lastMessage: 'Gostaria de agendar uma consulta',
    timestamp: '10:45',
    unreadCount: 2,
  },
  {
    id: '2',
    name: 'João Pedro',
    avatar: '',
    lastMessage: 'Obrigado pela confirmação!',
    timestamp: '09:30',
    unreadCount: 0,
  },
  {
    id: '3',
    name: 'Clínica Feliz',
    avatar: '',
    lastMessage: 'Perfeito, até amanhã!',
    timestamp: 'Ontem',
    unreadCount: 0,
  },
  {
    id: '4',
    name: 'Loja Fashion',
    avatar: '',
    lastMessage: 'Produto disponível em estoque',
    timestamp: 'Ontem',
    unreadCount: 0,
  },
  {
    id: '5',
    name: 'Roberto Costa',
    avatar: '',
    lastMessage: 'Muito obrigado pelo atendimento',
    timestamp: '15/03',
    unreadCount: 0,
  },
]

const mockMessages: Record<string, Message[]> = {
  '1': [
    {
      id: '1',
      conversationId: '1',
      content: 'Olá! Bem-vindo ao Neuralilux. Como posso ajudá-lo hoje?',
      timestamp: new Date('2024-03-26T10:30:00'),
      isOutgoing: false,
      status: 'read',
      sender: { name: 'Maria Silva' },
    },
    {
      id: '2',
      conversationId: '1',
      content: 'Gostaria de agendar uma consulta para amanhã',
      timestamp: new Date('2024-03-26T10:32:00'),
      isOutgoing: false,
      status: 'read',
      sender: { name: 'Maria Silva' },
    },
    {
      id: '3',
      conversationId: '1',
      content: 'Claro! Temos horários disponíveis às 14h e às 16h. Qual prefere?',
      timestamp: new Date('2024-03-26T10:33:00'),
      isOutgoing: true,
      status: 'read',
    },
    {
      id: '4',
      conversationId: '1',
      content: 'Prefiro às 14h, por favor',
      timestamp: new Date('2024-03-26T10:45:00'),
      isOutgoing: false,
      status: 'read',
      sender: { name: 'Maria Silva' },
    },
  ],
}

export default function ChatPage() {
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState(mockMessages)
  const [isTyping, setIsTyping] = useState(false)

  const activeConversation = mockConversations.find(
    (c) => c.id === activeConversationId
  )
  const activeMessages = activeConversationId
    ? messages[activeConversationId] || []
    : []

  const handleSendMessage = (content: string) => {
    if (!activeConversationId) return

    const newMessage: Message = {
      id: Date.now().toString(),
      conversationId: activeConversationId,
      content,
      timestamp: new Date(),
      isOutgoing: true,
      status: 'sending',
    }

    setMessages((prev) => ({
      ...prev,
      [activeConversationId]: [...(prev[activeConversationId] || []), newMessage],
    }))

    // Simulate message status updates
    setTimeout(() => {
      setMessages((prev) => ({
        ...prev,
        [activeConversationId]: prev[activeConversationId].map((msg) =>
          msg.id === newMessage.id ? { ...msg, status: 'sent' } : msg
        ),
      }))
    }, 1000)

    setTimeout(() => {
      setMessages((prev) => ({
        ...prev,
        [activeConversationId]: prev[activeConversationId].map((msg) =>
          msg.id === newMessage.id ? { ...msg, status: 'delivered' } : msg
        ),
      }))
    }, 2000)

    setTimeout(() => {
      setMessages((prev) => ({
        ...prev,
        [activeConversationId]: prev[activeConversationId].map((msg) =>
          msg.id === newMessage.id ? { ...msg, status: 'read' } : msg
        ),
      }))
    }, 3000)
  }

  return (
    <div className="flex h-screen bg-dark">
      <ChatSidebar
        conversations={mockConversations}
        activeConversationId={activeConversationId}
        onSelectConversation={setActiveConversationId}
      />
      <div className="flex flex-1 flex-col">
        {activeConversation ? (
          <>
            <ChatHeader
              name={activeConversation.name}
              avatar={activeConversation.avatar}
              status="Online"
            />
            <div className="flex-1 overflow-y-auto p-6">
              <div className="space-y-4">
                {activeMessages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
                {isTyping && <TypingIndicator />}
              </div>
            </div>
            <ChatInput onSendMessage={handleSendMessage} />
          </>
        ) : (
          <EmptyChat />
        )}
      </div>
    </div>
  )
}
