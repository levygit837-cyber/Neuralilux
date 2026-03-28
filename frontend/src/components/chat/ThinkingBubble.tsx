'use client'

import { useEffect, useRef } from 'react'
import { ChevronDown } from 'lucide-react'
import { renderStructuredAgentContent } from '@/components/agent/renderStructuredAgentContent'

interface ThinkingBubbleProps {
  tokens: string[]
  onCollapse: () => void
  isLive?: boolean
}

export function ThinkingBubble({ tokens, onCollapse, isLive = true }: ThinkingBubbleProps) {
  const contentRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom as tokens arrive
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [tokens])

  const fullText = tokens.join('')

  return (
    <div className="flex items-start gap-3 py-2">
      <div className="flex w-full max-w-[480px] flex-col gap-3 rounded-[18px] border border-[#8B5CF630] bg-[#120F27] p-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {/* Icon with 3 dots */}
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary">
              <div className="flex gap-[3px]">
                <span className="h-1 w-1 rounded-full bg-white" />
                <span className="h-1 w-1 rounded-full bg-white" />
                <span className="h-1 w-1 rounded-full bg-white" />
              </div>
            </div>

            {/* Meta text */}
            <span className="text-sm font-semibold text-text-light">Raciocínio</span>
          </div>

          {isLive && (
            <div className="flex items-center gap-1.5 rounded-full border border-[#8B5CF655] bg-[#8B5CF622] px-2.5 py-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#C4B5FD] animate-pulse" />
              <span className="text-xs font-semibold text-[#C4B5FD]">Ao vivo</span>
            </div>
          )}
        </div>

        {/* Content area - tokens streaming */}
        <div
          ref={contentRef}
          className="flex max-h-[200px] flex-col gap-2 overflow-y-auto"
        >
          {fullText ? (
            <div className="space-y-3 text-[#D5CAE9]">
              {renderStructuredAgentContent(fullText, { variant: 'compact' })}
              {isLive && (
                <span className="ml-0.5 inline-block h-4 w-[2px] animate-pulse bg-primary align-middle" />
              )}
            </div>
          ) : (
            // Placeholder lines when no tokens yet
            <div className="flex flex-col gap-2">
              <div className="h-2 w-full rounded-full bg-[#2A2346]" />
              <div className="h-2 w-full rounded-full bg-[#2A2346]" />
              <div className="h-2 w-[320px] rounded-full bg-[#2A2346]" />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-[#A7A1C5]">
            {isLive ? 'Baseado em contexto, memória e histórico recente.' : ''}
          </span>
          <button
            onClick={onCollapse}
            type="button"
            aria-label="Recolher raciocínio"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#3A2C70] bg-[#221A44] text-[#E9D5FF] transition-colors hover:bg-[#2D2255]"
          >
            <ChevronDown className="h-4 w-4 -rotate-90 transition-transform duration-200" />
          </button>
        </div>
      </div>
    </div>
  )
}
