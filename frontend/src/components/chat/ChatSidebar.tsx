import { SearchInput } from '@/components/ui/SearchInput'
import { ChatListItem } from './ChatListItem'
import type { Conversation } from '@/types/chat'

interface ChatSidebarProps {
  conversations: Conversation[]
  activeConversationId: string | null
  onSelectConversation: (id: string) => void
}

export function ChatSidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
}: ChatSidebarProps) {
  return (
    <div className="flex h-full w-[380px] flex-col border-r border-border-color bg-card">
      <div className="flex flex-col gap-4 p-6">
        <h1 className="text-2xl font-bold text-text-light">Conversas</h1>
        <SearchInput placeholder="Buscar..." />
      </div>
      <div className="flex-1 overflow-y-auto px-2">
        {conversations.map((conversation) => (
          <ChatListItem
            key={conversation.id}
            conversation={conversation}
            isActive={conversation.id === activeConversationId}
            onClick={() => onSelectConversation(conversation.id)}
          />
        ))}
      </div>
    </div>
  )
}
