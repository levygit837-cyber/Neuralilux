'use client'

import { useChatStore } from '@/stores/useChatStore'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ThinkingBubble } from './ThinkingBubble'
import { ThinkingCollapsed } from './ThinkingCollapsed'

interface ThinkingManagerProps {
  conversationId: string
}

export function ThinkingManager({ conversationId }: ThinkingManagerProps) {
  const thinkingEvent = useChatStore((state) => state.thinkingEvents[conversationId])
  const collapseThinking = useChatStore((state) => state.collapseThinking)
  const setThinkingState = useChatStore((state) => state.setThinkingState)
  const cancelClearTimer = useChatStore((state) => state.cancelClearTimer)

  if (!thinkingEvent || thinkingEvent.state === 'idle') {
    return null
  }

  const handleCollapse = () => {
    collapseThinking(conversationId)
  }

  const handleExpand = () => {
    setThinkingState(conversationId, 'streaming', thinkingEvent.summary)
    cancelClearTimer(conversationId)
  }

  switch (thinkingEvent.state) {
    case 'indicator':
      return <ThinkingIndicator />

    case 'streaming':
      return (
        <ThinkingBubble
          tokens={thinkingEvent.tokens || []}
          onCollapse={handleCollapse}
        />
      )

    case 'collapsed':
      return (
        <ThinkingCollapsed
          summary={thinkingEvent.summary || ''}
          onExpand={handleExpand}
        />
      )

    default:
      return null
  }
}
