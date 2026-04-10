import { ChatListItem } from './ChatListItem'
import type { Conversation } from '@/types/chat'
import { MagnifyingGlass, Plus, Funnel } from '@phosphor-icons/react'

interface ChatSidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  onSelectConversation: (id: string) => void
  isLoading?: boolean
}

export function ChatSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  isLoading,
}: ChatSidebarProps) {
  return (
    <section className="w-[380px] bg-brand-card border-r border-brand-border flex flex-col z-10 flex-shrink-0">
      {/* Header */}
      <div className="px-6 pt-6 pb-4">
        <div className="flex justify-between items-center mb-5">
          <h1 className="text-2xl font-bold tracking-tight text-content-light">Conversas</h1>
          <div className="flex gap-2">
            <button className="w-8 h-8 rounded-full bg-brand-base flex items-center justify-center hover:text-primary transition-colors border border-brand-border">
              <Plus weight="regular" className="text-lg" />
            </button>
            <button className="w-8 h-8 rounded-full bg-brand-base flex items-center justify-center hover:text-primary transition-colors border border-brand-border">
              <Funnel weight="regular" className="text-lg" />
            </button>
          </div>
        </div>

        {/* Search */}
        <div className="relative group">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-content-muted group-focus-within:text-primary transition-colors">
            <MagnifyingGlass weight="regular" className="text-lg" />
          </div>
          <input 
            type="text" 
            placeholder="Buscar contatos ou mensagens..." 
            className="w-full bg-brand-base text-content-light placeholder-content-muted rounded-xl py-2.5 pl-10 pr-4 text-sm border border-brand-border focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/50 transition-all shadow-[inset_0_2px_4px_rgba(0,0,0,0.3)]"
          />
        </div>

        {/* Filters - will be replaced with ContactFilters component */}
        <div className="flex gap-2 mt-4 overflow-x-auto pb-1 scrollbar-hide">
          <button className="px-4 py-1.5 rounded-full bg-primary/20 text-primary border border-primary/30 text-sm font-medium whitespace-nowrap transition-colors">Todas</button>
          <button className="px-4 py-1.5 rounded-full bg-brand-base text-content-gray border border-brand-border text-sm font-medium whitespace-nowrap hover:bg-brand-hover transition-colors">Não lidas <span className="ml-1 bg-brand-card px-1.5 rounded text-xs">5</span></button>
          <button className="px-4 py-1.5 rounded-full bg-brand-base text-content-gray border border-brand-border text-sm font-medium whitespace-nowrap hover:bg-brand-hover transition-colors">Grupos</button>
          <button className="px-4 py-1.5 rounded-full bg-brand-base text-content-gray border border-brand-border text-sm font-medium whitespace-nowrap hover:bg-brand-hover transition-colors">IA Ativa</button>
        </div>
      </div>

      {/* Contact List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : conversations.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-sm text-content-muted">
            Nenhuma conversa encontrada
          </div>
        ) : (
          conversations.map((conversation) => (
            <ChatListItem
              key={conversation.id}
              conversation={conversation}
              isActive={conversation.id === activeConversationId}
              onClick={() => onSelectConversation(conversation.id)}
            />
          ))
        )}
      </div>
    </section>
  )
}
