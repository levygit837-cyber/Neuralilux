import type { Conversation } from '@/types/chat'
import { cn } from '@/lib/utils'
import { Microphone, Image } from '@phosphor-icons/react'
import { useState } from 'react'

interface ChatListItemProps {
  conversation: Conversation
  isActive?: boolean
  onClick?: () => void
}

export function ChatListItem({ conversation, isActive, onClick }: ChatListItemProps) {
  const isTyping = conversation.isTyping
  const isGroup = conversation.isGroup
  const isBot = conversation.isBot
  const hasUnread = conversation.unreadCount > 0
  const [imageError, setImageError] = useState(false)

  return (
    <div
      onClick={onClick}
      className={cn(
        'p-3 rounded-xl cursor-pointer relative overflow-hidden flex items-center gap-3 group transition-colors',
        isActive
          ? 'bg-brand-hover/80 border border-primary/20'
          : 'hover:bg-brand-hover border border-transparent'
      )}
    >
      {/* Active left indicator */}
      {isActive && (
        <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary shadow-[0_0_10px_#8B5CF6]" />
      )}

      {/* Avatar */}
      <div className="relative flex-shrink-0">
        {isGroup && conversation.groupAvatars ? (
          <div className="relative w-12 h-12 rounded-full bg-brand-base border border-brand-border flex items-center justify-center overflow-hidden">
            <div className="grid grid-cols-2 gap-0.5 w-full h-full p-1">
              {conversation.groupAvatars.slice(0, 4).map((avatar, index) => (
                <img
                  key={index}
                  src={avatar}
                  alt=""
                  className="w-full h-full object-cover rounded-full"
                  onError={() => setImageError(true)}
                />
              ))}
            </div>
          </div>
        ) : (
          <div className="relative w-12 h-12 rounded-full border-2 border-brand-base overflow-hidden">
            {conversation.avatar && !imageError ? (
              <img
                src={conversation.avatar}
                alt={conversation.name}
                className="w-full h-full object-cover"
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="w-full h-full bg-gradient-to-br from-primary to-primary-dark flex items-center justify-center text-white font-bold text-lg">
                {conversation.name.substring(0, 2).toUpperCase()}
              </div>
            )}
          </div>
        )}
        {conversation.isOnline && (
          <div className="absolute bottom-0 right-0 w-3.5 h-3.5 bg-status-success border-2 border-brand-hover rounded-full online-pulse z-10" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-center mb-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-content-light truncate text-[15px]">{conversation.name}</h3>
            {isBot && (
              <span className="bg-accent/10 border border-accent/20 text-accent text-[8px] uppercase tracking-wider px-1.5 py-0.5 rounded font-bold">Bot</span>
            )}
          </div>
          <span className={cn('text-xs', isActive ? 'text-primary font-medium' : 'text-content-muted')}>
            {conversation.timestamp}
          </span>
        </div>
        <div className="flex justify-between items-center">
          {isTyping ? (
            <div className="text-sm text-primary flex items-center gap-1">
              <span className="flex gap-[2px]">
                <div className="w-1 h-1 bg-primary rounded-full dot-1" />
                <div className="w-1 h-1 bg-primary rounded-full dot-2" />
                <div className="w-1 h-1 bg-primary rounded-full dot-3" />
              </span>
              <span className="text-[13px] italic">Digitando...</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 text-content-muted">
              {/* Show icon based on message type */}
              {conversation.lastMessage.includes('audio') && (
                <Microphone weight="fill" className="text-primary text-sm" />
              )}
              {conversation.lastMessage.includes('.jpg') && (
                <Image weight="regular" className="text-content-muted text-sm" />
              )}
              <p className="text-sm truncate text-[13px]">{conversation.lastMessage}</p>
            </div>
          )}
          {hasUnread && (
            <span className="bg-primary text-white text-[10px] font-bold w-5 h-5 flex items-center justify-center rounded-full shadow-glow">
              {conversation.unreadCount}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
