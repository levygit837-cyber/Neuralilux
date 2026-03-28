'use client'

import type { AgentMessage as AgentMessageType } from '@/types/agent'

interface UserMessageProps {
  message: AgentMessageType
}

export function UserMessage({ message }: UserMessageProps) {
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="flex justify-end">
      <div className="flex max-w-[70%] flex-col items-end gap-1">
        <div className="rounded-2xl rounded-tr-md bg-primary px-4 py-3">
          <p className="text-sm text-white">{message.content}</p>
        </div>
        <span className="text-xs text-gray-500">{formatTime(message.timestamp)}</span>
      </div>
    </div>
  )
}