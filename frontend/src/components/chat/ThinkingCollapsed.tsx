'use client'

import { CaretDown } from '@phosphor-icons/react'

interface ThinkingCollapsedProps {
  summary?: string
  onExpand: () => void
}

export function ThinkingCollapsed({ summary, onExpand }: ThinkingCollapsedProps) {
  return (
    <div className="flex items-start gap-3 py-2">
      <div className="flex w-full max-w-[480px] items-start justify-between gap-3 rounded-[16px] border border-primary/20 bg-brand-deep px-3.5 py-3">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          {/* Icon with 3 dots */}
          <div className="mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary">
            <div className="flex gap-[3px]">
              <span className="h-1 w-1 rounded-full bg-white" />
              <span className="h-1 w-1 rounded-full bg-white" />
              <span className="h-1 w-1 rounded-full bg-white" />
            </div>
          </div>

          {/* Text group */}
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="text-sm font-semibold text-content-light">Pensamento oculto</span>
            <p className="mt-1 text-xs leading-relaxed text-content-subtle">
              {summary || 'Resumo do raciocínio disponível para expandir.'}
            </p>
          </div>
        </div>

        {/* Right side - expand button */}
        <button
          onClick={onExpand}
          type="button"
          aria-label="Expandir raciocínio"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-primary-edge bg-primary-deep text-primary-pale transition-colors hover:bg-primary-strong"
        >
          <CaretDown weight="bold" className="text-lg transition-transform duration-200" />
        </button>
      </div>
    </div>
  )
}
