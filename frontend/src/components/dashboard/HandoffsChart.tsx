'use client'

import { Card } from '@/components/ui/Card'
import { WidgetError } from '@/components/dashboard/WidgetError'
import type { HandoffsByStatus } from '@/types/dashboard'

interface HandoffsChartProps {
  /** `undefined` enquanto carrega. */
  data?: HandoffsByStatus
  error?: string | null
  onRetry: () => void
}

interface Segment {
  key: keyof HandoffsByStatus
  label: string
  color: string
}

const SEGMENTS: Segment[] = [
  { key: 'open', label: 'Abertos', color: 'rgb(var(--color-status-warning))' },
  { key: 'in_progress', label: 'Em atendimento', color: 'rgb(var(--color-status-info))' },
  { key: 'closed', label: 'Devolvidos ao Agent', color: 'rgb(var(--color-status-success))' },
  { key: 'expired', label: 'Expirados', color: 'rgb(var(--color-accent))' },
]

const RADIUS = 40
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/** Tickets abertos no período, por status. O total é o número de Handoffs do período. */
export function HandoffsChart({ data, error, onRetry }: HandoffsChartProps) {
  const total = data ? SEGMENTS.reduce((sum, s) => sum + data[s.key], 0) : 0
  let offset = 0
  const arcs = data
    ? SEGMENTS.map((segment) => {
        const length = total > 0 ? (data[segment.key] / total) * CIRCUMFERENCE : 0
        const arc = { ...segment, count: data[segment.key], length, offset }
        offset += length
        return arc
      })
    : []

  return (
    <Card className="flex h-[380px] animate-slide-up flex-col delay-500">
      <div className="mb-2">
        <h3 className="font-medium text-content-light">Handoffs</h3>
        <p className="mt-1 text-xs text-content-muted">Tickets abertos no período, por status</p>
      </div>

      {error ? (
        <div className="flex-1">
          <WidgetError message={error} onRetry={onRetry} />
        </div>
      ) : !data ? (
        <div className="flex flex-1 items-center justify-center" aria-busy="true">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : (
        <>
          <div className="relative flex flex-1 items-center justify-center">
            <svg width="200" height="200" viewBox="0 0 100 100" className="-rotate-90" role="img" aria-label={`${total} Handoffs no período`}>
              <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="rgb(var(--color-brand-border))" strokeWidth="10" />
              {arcs.map((arc) =>
                arc.length > 0 ? (
                  <circle
                    key={arc.key}
                    cx="50"
                    cy="50"
                    r={RADIUS}
                    fill="none"
                    stroke={arc.color}
                    strokeWidth="10"
                    strokeDasharray={`${arc.length} ${CIRCUMFERENCE}`}
                    strokeDashoffset={-arc.offset}
                    className="donut-segment"
                  />
                ) : null
              )}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold text-content-light">{total}</span>
              <span className="mt-1 text-[0.65rem] font-semibold uppercase tracking-wider text-content-muted">Handoffs</span>
            </div>
          </div>

          <ul className="mt-4 grid grid-cols-2 gap-2 border-t border-brand-border/50 pt-4">
            {arcs.map((arc) => (
              <li key={arc.key} className="flex items-center gap-2 text-xs text-content-muted">
                <span className="h-3 w-3 rounded-full" style={{ backgroundColor: arc.color }} aria-hidden="true" />
                {arc.label}: <span className="font-semibold text-content-light">{arc.count}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}
