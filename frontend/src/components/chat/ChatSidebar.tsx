import { useEffect, useState } from 'react'
import { ChatListItem } from './ChatListItem'
import type { ChatCounts, Conversation, ConversationCategory } from '@/types/chat'
import { ArrowsClockwise, MagnifyingGlass } from '@phosphor-icons/react'
import { cn } from '@/lib/utils'

/** Espera depois da última tecla antes de a busca ir ao backend. */
const SEARCH_DEBOUNCE_MS = 300

const FILTERS: { category: ConversationCategory; label: string; empty: string }[] = [
  { category: 'all', label: 'Todas', empty: 'Nenhuma conversa encontrada' },
  { category: 'unread', label: 'Não lidas', empty: 'Nenhuma conversa não lida' },
  { category: 'groups', label: 'Grupos', empty: 'Nenhum grupo encontrado' },
  { category: 'ai', label: 'IA Ativa', empty: 'Nenhuma conversa com a IA ativa' },
  { category: 'human', label: 'Humano', empty: 'Nenhuma conversa com atendente humano' },
]

interface ChatSidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  onSelectConversation: (id: string) => void
  isLoading?: boolean
  category: ConversationCategory
  onCategoryChange: (category: ConversationCategory) => void
  /** Busca aplicada. O campo guarda o rascunho; quem monta o componente usa `key` para reiniciá-lo. */
  search: string
  onSearchChange: (search: string) => void
  counts: ChatCounts | null
  isSyncing: boolean
  onSync: () => void
  hasMore: boolean
  isLoadingMore: boolean
  onLoadMore: () => void
  /** Abaixo de `lg` a lista e a conversa alternam; com a conversa aberta, a lista some. */
  hiddenOnMobile: boolean
}

export function ChatSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  isLoading,
  category,
  onCategoryChange,
  search,
  onSearchChange,
  counts,
  isSyncing,
  onSync,
  hasMore,
  isLoadingMore,
  onLoadMore,
  hiddenOnMobile,
}: ChatSidebarProps) {
  const [draft, setDraft] = useState(search)

  useEffect(() => {
    if (draft === search) return
    const timer = setTimeout(() => onSearchChange(draft), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [draft, search, onSearchChange])

  const emptyText = search.trim()
    ? 'Nenhuma conversa encontrada para a busca'
    : (FILTERS.find((filter) => filter.category === category)?.empty ?? 'Nenhuma conversa encontrada')

  return (
    <section
      aria-label="Conversas"
      className={cn(
        'w-full lg:w-[380px] bg-brand-card border-r border-brand-border flex-col z-10 flex-shrink-0 min-h-0',
        hiddenOnMobile ? 'hidden lg:flex' : 'flex'
      )}
    >
      {/* Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex justify-between items-center mb-5">
          <h1 className="text-2xl font-bold tracking-tight text-content-light">Conversas</h1>
          <button
            type="button"
            onClick={onSync}
            disabled={isSyncing}
            aria-busy={isSyncing}
            aria-label="Sincronizar histórico"
            title="Sincronizar histórico"
            className="w-8 h-8 rounded-full bg-brand-base flex items-center justify-center hover:text-primary-light transition-colors border border-brand-border disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <ArrowsClockwise weight="regular" aria-hidden="true" className={cn('text-lg', isSyncing && 'animate-spin')} />
          </button>
        </div>

        {/* Search */}
        <div className="relative group">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-content-muted group-focus-within:text-primary-light transition-colors">
            <MagnifyingGlass weight="regular" aria-hidden="true" className="text-lg" />
          </div>
          <input
            type="search"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            aria-label="Buscar contatos ou mensagens"
            placeholder="Buscar contatos ou mensagens..."
            className="w-full bg-brand-base text-content-light placeholder-content-muted rounded-xl py-2.5 pl-10 pr-4 text-sm border border-brand-border focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)]"
          />
        </div>

        {/* Filters */}
        <div role="group" aria-label="Filtrar conversas" className="relative flex gap-2 mt-4 overflow-x-auto pb-1 scrollbar-hide">
          {FILTERS.map(({ category: value, label }) => {
            const isActive = value === category
            const count = counts?.[value] ?? 0
            return (
              <button
                key={value}
                type="button"
                aria-pressed={isActive}
                onClick={() => onCategoryChange(value)}
                className={cn(
                  'px-4 py-1.5 rounded-full border text-sm font-medium whitespace-nowrap transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                  isActive
                    ? 'bg-primary/20 text-primary-light border-primary/30'
                    : 'bg-brand-base text-content-gray border-brand-border hover:bg-brand-hover'
                )}
              >
                {label}
                {count > 0 && (
                  <>
                    <span className="sr-only">, </span>
                    <span className="ml-1 bg-brand-card px-1.5 rounded text-xs">{count}</span>
                  </>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Contact List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-sm text-content-muted">{emptyText}</div>
        ) : (
          <>
            {conversations.map((conversation) => (
              <ChatListItem
                key={conversation.id}
                conversation={conversation}
                isActive={conversation.id === activeConversationId}
                onClick={() => onSelectConversation(conversation.id)}
              />
            ))}
            {hasMore && (
              <button
                type="button"
                onClick={onLoadMore}
                disabled={isLoadingMore}
                aria-busy={isLoadingMore}
                className="w-full rounded-xl border border-brand-border bg-brand-base py-2 text-sm font-medium text-content-gray transition-colors hover:bg-brand-hover disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {isLoadingMore ? 'Carregando...' : 'Carregar mais'}
              </button>
            )}
          </>
        )}
      </div>
    </section>
  )
}
