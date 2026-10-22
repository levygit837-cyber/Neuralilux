'use client'

import { useChatStore } from '@/stores/useChatStore'
import { useAuthStore } from '@/stores/useAuthStore'
import { useResolvedInstance } from '@/hooks/useResolvedInstance'
import { useAgentControl } from '@/hooks/useAgentControl'
import { useChatRealtime } from '@/hooks/useChatRealtime'
import { useChatData } from '@/hooks/useChatData'
import { ChatSidebar } from './ChatSidebar'
import { ChatHeader } from './ChatHeader'
import { MessagePane } from './MessagePane'
import { EmptyChat } from './EmptyChat'

function Banner({ text, tone }: { text: string; tone: 'warning' | 'error' }) {
  const colors = tone === 'error' ? 'border-error/20 bg-error/10 text-error' : 'border-warning/20 bg-warning/10 text-warning'
  return (
    <div role="alert" className={`border-b px-6 py-3 text-sm ${colors}`}>
      {text}
    </div>
  )
}

export function WhatsAppChat() {
  const token = useAuthStore((state) => state.token)
  const conversations = useChatStore((state) => state.conversations)
  const activeConversationId = useChatStore((state) => state.activeConversationId)
  const isLoadingConversations = useChatStore((state) => state.isLoadingConversations)
  const isTyping = useChatStore((state) => state.typingIndicators[state.activeConversationId ?? ''] ?? false)
  const error = useChatStore((state) => state.error)
  const setActiveConversation = useChatStore((state) => state.setActiveConversation)

  const { resolvedInstance, isResolvingInstance, resolveError } = useResolvedInstance()
  const instanceName = resolvedInstance?.name
  const agent = useAgentControl(instanceName, token)

  const { isConnected } = useChatRealtime({
    token,
    instanceName,
    openConversationJid: conversations.find((item) => item.id === activeConversationId)?.remoteJid,
  })
  const { activeConversation, sendMessage, retryMessage } = useChatData(resolvedInstance?.id, isConnected)

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
        onSelectConversation={setActiveConversation}
        isLoading={isLoadingConversations}
      />
      <div className="flex-1 flex flex-col min-h-0 relative overflow-hidden">
        <div className="absolute inset-0 chat-pattern opacity-80 pointer-events-none z-0" />
        <div className="relative z-10 flex flex-col h-full">
          {resolveError && <Banner tone="error" text={resolveError} />}
          {error && <Banner tone="error" text={error} />}
          {activeConversation ? (
            <>
              <ChatHeader
                name={activeConversation.name}
                avatar={activeConversation.avatar}
                status={isTyping ? 'digitando...' : activeConversation.isOnline ? 'Online' : 'Offline'}
                isOnline={activeConversation.isOnline}
                humanHandoff={activeConversation.humanHandoff}
                agentEnabled={agent.agentEnabled}
                agentName={agent.selectedAgentName}
                availableAgents={agent.availableAgents}
                selectedAgentId={agent.selectedAgentId}
                onSelectAgent={agent.selectAgent}
                onToggleAgent={agent.toggleAgent}
                isAgentLoading={agent.isAgentLoading}
                isAgentBindingLoading={agent.isBindingLoading}
              />
              {agent.error && <Banner tone="warning" text={agent.error} />}
              <MessagePane
                conversationId={activeConversation.id}
                onSendMessage={sendMessage}
                onRetryMessage={retryMessage}
              />
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <EmptyChat />
            </div>
          )}
        </div>
      </div>
      {!isConnected && (
        <div
          role="status"
          className="fixed bottom-4 right-4 rounded-lg bg-brand-card/90 border border-brand-border px-4 py-2 text-sm text-content-muted backdrop-blur-sm"
        >
          <span aria-hidden="true" className="inline-block w-2 h-2 rounded-full bg-yellow-500 mr-2 animate-pulse" />
          Conectando ao servidor...
        </div>
      )}
    </div>
  )
}
