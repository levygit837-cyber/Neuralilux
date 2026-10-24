'use client'

import { useCallback, useEffect, useRef } from 'react'
import { selectActiveConversation, useChatStore } from '@/stores/useChatStore'
import { useAuthStore } from '@/stores/useAuthStore'
import { useResolvedInstance } from '@/hooks/useResolvedInstance'
import { useAgentControl } from '@/hooks/useAgentControl'
import { useChatRealtime } from '@/hooks/useChatRealtime'
import { useChatData } from '@/hooks/useChatData'
import { useHandoffControl } from '@/hooks/useHandoffControl'
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
  const openConversationJid = useChatStore((state) => selectActiveConversation(state)?.remoteJid)
  const setActiveConversation = useChatStore((state) => state.setActiveConversation)
  const isActiveExplicit = useChatStore((state) => state.isActiveExplicit)
  const category = useChatStore((state) => state.category)
  const search = useChatStore((state) => state.search)
  const counts = useChatStore((state) => state.counts)
  const isSyncing = useChatStore((state) => state.isSyncing)
  const setCategory = useChatStore((state) => state.setCategory)
  const setSearch = useChatStore((state) => state.setSearch)
  const hasMore = useChatStore((state) => state.conversations.length < state.totalConversations)
  const isLoadingMore = useChatStore((state) => state.isLoadingMore)

  const { resolvedInstance, isResolvingInstance, resolveError } = useResolvedInstance()
  const instanceName = resolvedInstance?.name
  const agent = useAgentControl(instanceName, token)
  const handoff = useHandoffControl(activeConversationId)

  const { isConnected } = useChatRealtime({
    token,
    instanceName,
    openConversationJid,
  })
  const { activeConversation, sendMessage, retryMessage, syncHistory, loadMoreConversations } = useChatData(
    resolvedInstance?.id,
    isConnected
  )

  // Abaixo de `lg` a lista e a conversa alternam: só a escolha do usuário abre a conversa (a primeira,
  // aberta sozinha no desktop, não esconde a lista).
  const showConversation = Boolean(activeConversation) && isActiveExplicit
  const returnFocusId = useRef<string | null>(null)

  const backToList = useCallback(() => {
    returnFocusId.current = useChatStore.getState().activeConversationId
    setActiveConversation(null)
  }, [setActiveConversation])

  // Devolve o foco ao item de onde a conversa foi aberta, quando a lista volta a aparecer.
  useEffect(() => {
    const id = returnFocusId.current
    if (showConversation || !id) return
    returnFocusId.current = null
    document.querySelector<HTMLElement>(`[data-conversation-id="${CSS.escape(id)}"]`)?.focus()
  }, [showConversation, conversations])

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
        key={resolvedInstance?.id}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={setActiveConversation}
        isLoading={isLoadingConversations}
        category={category}
        onCategoryChange={setCategory}
        search={search}
        onSearchChange={setSearch}
        counts={counts}
        isSyncing={isSyncing}
        onSync={() => void syncHistory()}
        hasMore={hasMore}
        isLoadingMore={isLoadingMore}
        onLoadMore={() => void loadMoreConversations()}
        hiddenOnMobile={showConversation}
      />
      <div
        className={`flex-1 flex-col min-h-0 min-w-0 relative overflow-hidden ${showConversation ? 'flex' : 'hidden lg:flex'}`}
      >
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
                handoffAssigned={Boolean(activeConversation.handoffAssignedTo)}
                onTakeControl={() => void handoff.take(activeConversation.id)}
                onReleaseControl={() => void handoff.release(activeConversation.id)}
                isHandoffPending={handoff.pending}
                agentEnabled={agent.agentEnabled}
                agentName={agent.selectedAgentName}
                availableAgents={agent.availableAgents}
                selectedAgentId={agent.selectedAgentId}
                onSelectAgent={agent.selectAgent}
                onToggleAgent={agent.toggleAgent}
                isAgentLoading={agent.isAgentLoading}
                isAgentBindingLoading={agent.isBindingLoading}
                onBack={backToList}
              />
              {agent.error && <Banner tone="warning" text={agent.error} />}
              {handoff.error && <Banner tone="error" text={handoff.error} />}
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
