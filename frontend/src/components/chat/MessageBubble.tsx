import { MessageStatus } from './MessageStatus'
import type { Message } from '@/types/chat'
import { cn } from '@/lib/utils'
import { Check } from '@phosphor-icons/react'
import { useState } from 'react'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const time = new Date(message.timestamp).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
  })
  const [imageError, setImageError] = useState(false)

  // Handle different message types
  if (message.messageType === 'system') {
    return null // System messages should be handled by a separate component
  }

  if (message.messageType === 'audio') {
    return null // Audio messages should be handled by AudioMessage component
  }

  if (message.messageType === 'image') {
    return null // Image messages should be handled by ImageMessage component
  }

  if (message.messageType === 'video') {
    return null // Video messages should be handled by VideoMessage component
  }

  return (
    <div
      className={cn(
        'flex gap-3 max-w-[70%] group',
        message.isOutgoing ? 'self-end justify-end' : 'justify-start'
      )}
    >
      {!message.isOutgoing && message.sender && (
        <div className="w-8 h-8 rounded-full border border-brand-border mt-auto overflow-hidden">
          {message.sender.avatar && !imageError ? (
            <img
              src={message.sender.avatar}
              alt={message.sender.name}
              className="w-full h-full object-cover"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center text-white font-bold text-xs">
              {message.sender.name.substring(0, 2).toUpperCase()}
            </div>
          )}
        </div>
      )}
      <div className={cn('flex flex-col gap-1', message.isOutgoing ? 'items-end' : 'items-start')}>
        <div
          className={cn(
            'px-4 py-3 rounded-2xl text-[15px] leading-relaxed relative shadow-sm',
            message.isOutgoing
              ? 'bg-gradient-to-br from-primary-dark to-primary text-white shadow-glow-strong rounded-br-sm border border-primary-light/20'
              : 'bg-brand-card border border-brand-border/80 text-content-light rounded-bl-sm'
          )}
        >
          {message.content}
        </div>
        <div className={cn('flex items-center gap-1', message.isOutgoing ? 'mr-1' : 'ml-1')}>
          <span className="text-[11px] text-content-muted opacity-0 group-hover:opacity-100 transition-opacity">{time}</span>
          {message.isOutgoing && (
            <div className="flex items-center gap-0.5">
              {message.status === 'read' ? (
                <Check weight="fill" className="text-blue-400 text-sm" />
              ) : message.status === 'delivered' ? (
                <Check weight="fill" className="text-content-muted text-sm" />
              ) : (
                <Check weight="regular" className="text-content-muted text-sm" />
              )}
              {(message.status === 'read' || message.status === 'delivered') && (
                <Check weight="fill" className={message.status === 'read' ? 'text-blue-400 text-sm' : 'text-content-muted text-sm'} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
