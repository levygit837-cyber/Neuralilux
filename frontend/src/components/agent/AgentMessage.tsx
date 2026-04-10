'use client'

import type { AgentMessage as AgentMessageType } from '@/types/agent'
import { AgentThinkingPill } from './AgentThinkingPill'
import { AgentThinkingCard } from './AgentThinkingCard'
import { AgentToolCard } from './AgentToolCard'
import { AgentOutputMessage } from './AgentOutputMessage'
import { TimelineConnector } from './TimelineConnector'
import { UserMessage } from './UserMessage'

interface AgentMessageProps {
  message: AgentMessageType
  onExpandThinking?: (thinkingId: string) => void
  onCollapseThinking?: (thinkingId: string) => void
}

function EventRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex w-full justify-start pl-12 pr-4 relative">
      <TimelineConnector variant="through" topOffset="-32px" bottomOffset="-32px" />
      {children}
    </div>
  )
}

export function AgentMessage({ message, onExpandThinking, onCollapseThinking }: AgentMessageProps) {
  if (message.blockType === 'thinking_indicator') {
    return (
      <EventRow>
        <AgentThinkingPill isLive />
      </EventRow>
    )
  }

  if (message.blockType === 'thinking_streaming') {
    return (
      <EventRow>
        <AgentThinkingCard
          tokens={message.thinkingTokens ?? []}
          isLive={message.thinkingLive ?? false}
          durationSeconds={message.thinkingDurationSeconds}
          onCollapse={() => onCollapseThinking?.(message.id)}
        />
      </EventRow>
    )
  }

  if (message.blockType === 'thinking_collapsed') {
    return (
      <EventRow>
        <AgentThinkingPill
          summary={message.thinkingSummary}
          durationSeconds={message.thinkingDurationSeconds}
          onExpand={() => onExpandThinking?.(message.id)}
        />
      </EventRow>
    )
  }

  if (message.blockType === 'tool_result' && message.toolEvent) {
    return (
      <EventRow>
        <AgentToolCard toolEvent={message.toolEvent} />
      </EventRow>
    )
  }

  if (!message.isAgent) {
    return <UserMessage message={message} />
  }

  return <AgentOutputMessage message={message} />
}
