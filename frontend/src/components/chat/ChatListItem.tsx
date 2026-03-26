import { Avatar } from '@/components/ui/Avatar'
import { Badge } from '@/components/ui/Badge'
import type { Conversation } from '@/types/chat'
import { cn } from '@/lib/utils'

interface ChatListItemProps {
  conversation: Conversation
  isActive?: boolean
  onClick?: () => void
}

export function ChatListItem({ conversation, isActive, onClick }: ChatListItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-3 rounded-md p-4 text-left transition-colors hover:bg-hover',
        isActive && 'bg-hover'
      )}
    >
      <Avatar
        src={conversation.avatar}
        fallback={conversation.name.substring(0, 2).toUpperCase()}
        size="md"
      />
      <div className="flex-1 overflow-hidden">
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-sm font-semibold text-text-light">
            {conversation.name}
          </p>
          <span className="text-xs text-text-muted">{conversation.timestamp}</span>
        </div>
        <p className="truncate text-sm text-text-gray">{conversation.lastMessage}</p>
      </div>
      {conversation.unreadCount > 0 && (
        <Badge count={conversation.unreadCount} className="absolute right-4 top-4" />
      )}
    </button>
  )
}
