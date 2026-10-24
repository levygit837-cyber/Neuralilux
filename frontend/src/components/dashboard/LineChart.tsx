'use client'

import { Card } from '@/components/ui/Card'
import { WidgetError } from '@/components/dashboard/WidgetError'
import type { ConversationTimeSeriesPoint, DashboardPeriod } from '@/types/dashboard'

interface LineChartProps {
  /** Um ponto por dia local do período, com os dias sem Conversation em zero. `undefined` enquanto carrega. */
  data?: ConversationTimeSeriesPoint[]
  period: DashboardPeriod
  error?: string | null
  onRetry: () => void
}

const VIEWPORT_WIDTH = 600
const VIEWPORT_HEIGHT = 180
const PADDING_TOP = 10

/** `YYYY-MM-DD` é um dia do calendário: ao meio-dia local nenhum fuso do browser o empurra para o dia vizinho. */
function parseDay(day: string): Date {
  return new Date(`${day}T12:00:00`)
}

function pointY(count: number, maxCount: number): number {
  return PADDING_TOP + (1 - count / maxCount) * (VIEWPORT_HEIGHT - PADDING_TOP)
}

function buildSvgPath(points: ConversationTimeSeriesPoint[], maxCount: number): { line: string; area: string } {
  const coords = points.map((p, i) => ({
    x: points.length > 1 ? (i / (points.length - 1)) * VIEWPORT_WIDTH : VIEWPORT_WIDTH / 2,
    y: pointY(p.count, maxCount),
  }))
  let line = `M${coords[0].x},${coords[0].y}`
  for (let i = 1; i < coords.length; i++) {
    const prev = coords[i - 1]
    const curr = coords[i]
    const cpx = (prev.x + curr.x) / 2
    line += ` C${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`
  }
  const last = coords[coords.length - 1]
  const bottom = VIEWPORT_HEIGHT + PADDING_TOP
  return { line, area: `${line} L${last.x},${bottom} L${coords[0].x},${bottom} Z` }
}

function formatAxisDate(day: string, period: DashboardPeriod): string {
  const date = parseDay(day)
  if (period === '7d') return date.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '')
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }).replace('.', '')
}

export function LineChart({ data, period, error, onRetry }: LineChartProps) {
  const header = (
    <div className="mb-6">
      <h3 className="font-medium text-content-light">Conversas novas por dia</h3>
      <p className="mt-1 text-xs text-content-muted">Conversations criadas em cada dia do período</p>
    </div>
  )

  if (error) {
    return (
      <Card className="flex h-[380px] flex-col">
        {header}
        <div className="flex-1">
          <WidgetError message={error} onRetry={onRetry} />
        </div>
      </Card>
    )
  }

  if (!data) {
    return (
      <Card className="flex h-[380px] flex-col" aria-busy="true">
        {header}
        <div className="flex flex-1 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      </Card>
    )
  }

  const total = data.reduce((sum, p) => sum + p.count, 0)
  const maxCount = Math.max(...data.map((p) => p.count), 1)
  const { line, area } = data.length > 0 ? buildSvgPath(data, maxCount) : { line: '', area: '' }

  const step = Math.max(1, Math.floor(data.length / 6))
  const axisIndices: number[] = []
  for (let i = 0; i < data.length; i += step) axisIndices.push(i)
  if (data.length > 0 && axisIndices[axisIndices.length - 1] !== data.length - 1) axisIndices.push(data.length - 1)

  return (
    <Card className="flex h-[380px] animate-slide-up flex-col delay-400">
      {header}
      <div className="relative mt-4 w-full flex-1">
        {total === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center pb-6">
            <p className="text-xs text-content-muted">Nenhuma Conversation nova no período</p>
          </div>
        ) : (
          <svg
            viewBox={`0 0 ${VIEWPORT_WIDTH} ${VIEWPORT_HEIGHT + PADDING_TOP}`}
            className="relative z-10 h-[85%] w-full overflow-visible"
            role="img"
            aria-label={`${total} Conversations novas no período`}
          >
            <defs>
              <linearGradient id="lineStroke" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="rgb(var(--color-primary))" />
                <stop offset="100%" stopColor="rgb(var(--color-secondary))" />
              </linearGradient>
              <linearGradient id="lineArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(var(--color-primary))" stopOpacity="0.5" />
                <stop offset="100%" stopColor="rgb(var(--color-primary))" stopOpacity="0.0" />
              </linearGradient>
            </defs>
            <path d={area} fill="url(#lineArea)" className="opacity-80" />
            <path d={line} fill="none" stroke="url(#lineStroke)" strokeWidth="4" strokeLinecap="round" className="chart-path" />
            {data.map((p, i) => (
              <circle
                key={p.date}
                cx={data.length > 1 ? (i / (data.length - 1)) * VIEWPORT_WIDTH : VIEWPORT_WIDTH / 2}
                cy={pointY(p.count, maxCount)}
                r="3"
                fill="rgb(var(--color-primary))"
                stroke="rgb(var(--color-brand-base))"
                strokeWidth="2"
              >
                <title>{`${parseDay(p.date).toLocaleDateString('pt-BR')}: ${p.count}`}</title>
              </circle>
            ))}
          </svg>
        )}

        <div className="absolute bottom-0 flex w-full justify-between pt-2 text-[0.65rem] font-medium text-content-muted">
          {axisIndices.map((i) => (
            <span key={data[i].date}>{formatAxisDate(data[i].date, period)}</span>
          ))}
        </div>
      </div>
    </Card>
  )
}
