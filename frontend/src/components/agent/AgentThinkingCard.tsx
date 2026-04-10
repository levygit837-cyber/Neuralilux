'use client'

import { Brain, ChevronUp } from 'lucide-react'

interface AgentThinkingCardProps {
  tokens: string[]
  durationSeconds?: number
  isLive?: boolean
  onCollapse?: () => void
}

export function AgentThinkingCard({
  tokens,
  durationSeconds,
  isLive = false,
  onCollapse,
}: AgentThinkingCardProps) {
  return (
    <div className="w-full max-w-3xl bg-card border border-border-color rounded-xl overflow-hidden shadow-lg z-10">
      {/* Header */}
      <div className="flex items-center justify-between bg-hover px-4 py-2 border-b border-border-color">
        <div className="flex items-center gap-2">
          <Brain className="w-3.5 h-3.5 text-primary-light" />
          <span className="text-xs font-semibold text-primary-light uppercase tracking-wider">
            Pensamento do Agente
          </span>
          {isLive && (
            <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-primary/20 border border-primary/30 text-primary text-[10px] font-medium">
              <span className="w-1 h-1 rounded-full bg-primary animate-pulse" />
              ao vivo
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {durationSeconds != null && (
            <span className="text-xs font-mono text-text-muted">{durationSeconds.toFixed(1)}s</span>
          )}
          <button
            onClick={onCollapse}
            className="text-text-muted hover:text-text-light transition-colors"
            aria-label="Colapsar pensamento"
          >
            <ChevronUp className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="p-4 bg-[#0A0714] border-l-2 border-l-primary overflow-x-auto">
        <pre className="font-mono text-[13px] leading-relaxed text-text-muted whitespace-pre-wrap break-words">
          {tokens.map((token, i) => (
            <span key={i}>{token}</span>
          ))}
        </pre>
      </div>
    </div>
  )
}
