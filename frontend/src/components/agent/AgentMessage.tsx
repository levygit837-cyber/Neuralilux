'use client'

import { useState, useEffect } from 'react'
import { ThinkingIndicator } from '@/components/chat/ThinkingIndicator'
import { ThinkingBubble } from '@/components/chat/ThinkingBubble'
import { ThinkingCollapsed } from '@/components/chat/ThinkingCollapsed'
import type { AgentMessage as AgentMessageType } from '@/types/agent'
import { renderStructuredAgentContent } from './renderStructuredAgentContent'
import { ToolCollapsed } from './ToolCollapsed'

export function AgentMessage({ message, onExpandThinking, onCollapseThinking }: AgentMessageProps) {
  const [formattedTime, setFormattedTime] = useState<string>('')

  useEffect(() => {
    const time = message.timestamp.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
    })
    setFormattedTime(time)
  }, [message.timestamp])

  if (message.blockType === 'thinking_indicator') {
    return <ThinkingIndicator />
  }

  // Render thinking streaming block
  if (message.blockType === 'thinking_streaming') {
    return (
      <ThinkingBubble
        tokens={message.thinkingTokens || []}
        onCollapse={() => onCollapseThinking?.(message.id)}
        isLive={message.thinkingLive}
      />
    )
  }

  // Render thinking collapsed block
  if (message.blockType === 'thinking_collapsed') {
    return (
      <ThinkingCollapsed
        summary={message.thinkingSummary}
        onExpand={() => onExpandThinking?.(message.id)}
      />
    )
  }

  if (message.blockType === 'tool_result' && message.toolEvent) {
    return <ToolCollapsed toolEvent={message.toolEvent} />
  }

  // Render regular message
  const parsedContent = renderStructuredAgentContent(message.content, {
    variant: message.isAgent ? 'output' : 'default',
  })

  return (
    <div className="flex items-start gap-3">
      {message.isAgent && (
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-primary">
          <svg
            className="h-4 w-4 text-white"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        </div>
      )}
      <div className="flex max-w-[70%] flex-col gap-1">
        <div
          className={`rounded-2xl px-4 py-3 ${
            message.isAgent
              ? 'rounded-tl-md bg-hover'
              : 'rounded-tr-md bg-primary text-white'
          }`}
        >
          <div
            className={`space-y-2 ${
              message.isAgent ? 'text-text-light' : 'text-sm text-white'
            }`}
          >
            {parsedContent}
            {message.streaming && (
              <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-current align-middle opacity-80" />
            )}
          </div>
        </div>
        <span className="text-xs text-text-muted">{formattedTime}</span>
      </div>
    </div>
  )
}

interface AgentMessageProps {
  message: AgentMessageType
  onExpandThinking?: (thinkingId: string) => void
  onCollapseThinking?: (thinkingId: string) => void
}
