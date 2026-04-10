'use client'

import type { AgentMessage as AgentMessageType } from '@/types/agent'
import { renderStructuredAgentContent } from './renderStructuredAgentContent'
import { StreamingCursor } from './StreamingCursor'

interface AgentOutputMessageProps {
  message: AgentMessageType
}

export function AgentOutputMessage({ message }: AgentOutputMessageProps) {
  const parsedContent = renderStructuredAgentContent(message.content, { variant: 'output' })

  return (
    <div className="flex w-full justify-start relative">
      {/* Gradient line fading out below avatar (end of the event chain) */}
      <div className="absolute left-6 top-[-32px] bottom-4 w-px bg-gradient-to-b from-border-color to-transparent z-0" />

      {/* Avatar */}
      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary to-accent p-0.5 shrink-0 relative z-10 mt-1 shadow-glow">
        <div className="w-full h-full bg-card rounded-[10px] flex items-center justify-center">
          <svg className="w-6 h-6 text-text-light" fill="currentColor" viewBox="0 0 256 256">
            <path d="M200,48H136V16a8,8,0,0,0-16,0V48H56A32,32,0,0,0,24,80V192a32,32,0,0,0,32,32H200a32,32,0,0,0,32-32V80A32,32,0,0,0,200,48ZM172,96a12,12,0,1,1-12,12A12,12,0,0,1,172,96ZM96,96a12,12,0,1,1-12,12A12,12,0,0,1,96,96Zm88,80H72a8,8,0,0,1,0-16H184a8,8,0,0,1,0,16Z" />
          </svg>
        </div>
      </div>

      {/* Content */}
      <div className="ml-4 w-full max-w-3xl space-y-4 mt-1 text-text-gray">
        {parsedContent}
        {message.streaming && <StreamingCursor />}
      </div>
    </div>
  )
}
