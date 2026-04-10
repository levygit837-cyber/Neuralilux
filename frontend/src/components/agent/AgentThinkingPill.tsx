'use client'

import { Brain, ChevronDown } from 'lucide-react'

interface AgentThinkingPillProps {
  summary?: string
  durationSeconds?: number
  isLive?: boolean
  onExpand?: () => void
}

export function AgentThinkingPill({
  summary,
  durationSeconds,
  isLive = false,
  onExpand,
}: AgentThinkingPillProps) {
  if (isLive && !summary) {
    return (
      <button
        disabled
        className="bg-card border border-border-color text-text-muted text-xs px-3 py-1.5 rounded-full flex items-center gap-2 shadow-sm cursor-default"
      >
        <Brain className="w-3.5 h-3.5 text-primary shrink-0" />
        <span className="flex items-center gap-1">
          Pensando
          <span className="flex items-center gap-0.5 ml-0.5">
            <span className="w-1 h-1 rounded-full bg-primary-light dot-1" />
            <span className="w-1 h-1 rounded-full bg-primary-light dot-2" />
            <span className="w-1 h-1 rounded-full bg-primary-light dot-3" />
          </span>
        </span>
      </button>
    )
  }

  const label = durationSeconds != null ? `Pensou por ${durationSeconds}s` : (summary ?? 'Pensamento')

  return (
    <button
      onClick={onExpand}
      className="bg-card border border-border-color hover:border-primary/50 hover:bg-hover transition-all text-text-muted text-xs px-3 py-1.5 rounded-full flex items-center gap-2 cursor-pointer shadow-sm"
    >
      <Brain className="w-3.5 h-3.5 text-primary shrink-0" />
      <span>{label}</span>
      <ChevronDown className="w-3 h-3 ml-1 opacity-50" />
    </button>
  )
}
