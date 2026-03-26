import { Avatar } from '@/components/ui/Avatar'
import { MessageStatus } from './MessageStatus'
import type { Message } from '@/types/chat'
import { cn } from '@/lib/utils'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const time = new Date(message.timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  })

  return (
    <div
      className={cn(
        'flex gap-3',
        message.isOutgoing ? 'justify-end' : 'justify-start'
      )}
    >
      {!message.isOutgoing && message.sender && (
        <Avatar
          src={message.sender.avatar}
          fallback={message.sender.name.substring(0, 2).toUpperCase()}
          size="sm"
        />
      )}
      <div
        className={cn(
          'flex max-w-[480px] flex-col gap-2 rounded-md px-4 py-3',
          message.isOutgoing
            ? 'bg-primary text-text-light'
            : 'border border-border-color bg-card text-text-light'
        )}
      >
        <p className="text-sm">{message.content}</p>
        <div className="flex items-center justify-end gap-1">
          <span className="text-xs opacity-70">{time}</span>
          {message.isOutgoing && <MessageStatus status={message.status} />}
        </div>
      </div>
    </div>
  )
}
