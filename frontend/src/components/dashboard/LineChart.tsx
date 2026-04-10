'use client'

import { Card } from '@/components/ui/Card'
import type { ConversationTimeSeriesPoint } from '@/types/dashboard'

interface LineChartProps {
  data: ConversationTimeSeriesPoint[]
  period: '7d' | '30d' | '90d'
  onPeriodChange: (period: '7d' | '30d' | '90d') => void
  isLoading?: boolean
  className?: string
}

const VIEWPORT_WIDTH = 600
const VIEWPORT_HEIGHT = 180
const PADDING_TOP = 10

function buildSvgPath(points: ConversationTimeSeriesPoint[]): { line: string; area: string } {
  if (points.length === 0) return { line: '', area: '' }
  if (points.length === 1) {
    const y = VIEWPORT_HEIGHT / 2
    return {
      line: `M0,${y} L${VIEWPORT_WIDTH},${y}`,
      area: `M0,${y} L${VIEWPORT_WIDTH},${y} L${VIEWPORT_WIDTH},${VIEWPORT_HEIGHT + PADDING_TOP} L0,${VIEWPORT_HEIGHT + PADDING_TOP} Z`,
    }
  }

  const maxCount = Math.max(...points.map((p) => p.count), 1)
  const minCount = Math.min(...points.map((p) => p.count), 0)
  const range = maxCount - minCount || 1

  const normalized = points.map((p, i) => ({
    x: (i / (points.length - 1)) * VIEWPORT_WIDTH,
    y: PADDING_TOP + (1 - (p.count - minCount) / range) * (VIEWPORT_HEIGHT - PADDING_TOP),
  }))

  // Smooth cubic bezier path
  let line = `M${normalized[0].x},${normalized[0].y}`
  for (let i = 1; i < normalized.length; i++) {
    const prev = normalized[i - 1]
    const curr = normalized[i]
    const cpx = (prev.x + curr.x) / 2
    line += ` C${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`
  }

  const last = normalized[normalized.length - 1]
  const area = `${line} L${last.x},${VIEWPORT_HEIGHT + PADDING_TOP} L0,${VIEWPORT_HEIGHT + PADDING_TOP} Z`

  return { line, area }
}

function formatAxisDate(dateStr: string, period: '7d' | '30d' | '90d'): string {
  const d = new Date(dateStr)
  if (period === '7d') {
    return d.toLocaleDateString('pt-BR', { weekday: 'short' }).replace('.', '')
  }
  if (period === '30d') {
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' }).replace('.', '')
  }
  return d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '')
}

export function LineChart({ data, period, onPeriodChange, isLoading, className }: LineChartProps) {
  const timePeriods = [
    { value: '7d' as const, label: '7 dias' },
    { value: '30d' as const, label: '30 dias' },
    { value: '90d' as const, label: '90 dias' },
  ]

  const { line, area } = buildSvgPath(data)

  // Pick ~7 evenly spaced labels for the x-axis
  const axisLabels = (() => {
    if (data.length === 0) return []
    const step = Math.max(1, Math.floor(data.length / 6))
    const indices: number[] = []
    for (let i = 0; i < data.length; i += step) indices.push(i)
    if (indices[indices.length - 1] !== data.length - 1) {
      indices.push(data.length - 1)
    }
    return indices.map((i) => formatAxisDate(data[i].date, period))
  })()

  const lastPoint = data[data.length - 1]

  // Compute tooltip position for the last data point
  const lastNormX = data.length > 1 ? VIEWPORT_WIDTH : VIEWPORT_WIDTH / 2
  const maxCount = data.length > 0 ? Math.max(...data.map((p) => p.count), 1) : 1
  const minCount = data.length > 0 ? Math.min(...data.map((p) => p.count), 0) : 0
  const range = maxCount - minCount || 1
  const lastNormYPct = lastPoint
    ? ((1 - (lastPoint.count - minCount) / range) * 100).toFixed(0)
    : '50'

  return (
    <Card className={`flex flex-col h-[380px] animate-slide-up delay-400 ${className}`}>
      <div className="flex justify-between items-start mb-6">
        <div>
          <h3 className="font-medium text-text-light">Conversas ao Longo do Tempo</h3>
          <p className="text-xs text-text-muted mt-1">Volume diário de interações via IA</p>
        </div>
        <div className="flex bg-dark rounded-md p-1 border border-border-color">
          {timePeriods.map((p) => (
            <button
              key={p.value}
              onClick={() => onPeriodChange(p.value)}
              className={`px-3 py-1 text-xs font-medium rounded transition ${
                period === p.value
                  ? 'bg-card border border-border-color text-text-light shadow-sm'
                  : 'text-text-muted hover:text-text-light transition'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 relative w-full mt-4">
        {/* Background Grid Lines */}
        <div className="absolute inset-0 flex flex-col justify-between z-0 pb-6 opacity-20 pointer-events-none">
          <div className="border-b border-border-color w-full flex-1" />
          <div className="border-b border-border-color w-full flex-1" />
          <div className="border-b border-border-color w-full flex-1" />
          <div className="border-b border-border-color w-full flex-1" />
          <div className="w-full flex-1" />
        </div>

        {isLoading || data.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center pb-6">
            {isLoading ? (
              <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            ) : (
              <p className="text-xs text-text-muted">Sem dados para o período selecionado</p>
            )}
          </div>
        ) : (
          <>
            {/* SVG Line + Area Chart */}
            <svg
              viewBox={`0 0 ${VIEWPORT_WIDTH} ${VIEWPORT_HEIGHT + PADDING_TOP}`}
              className="w-full h-full preserve-3d z-10 relative overflow-visible"
            >
              <defs>
                <linearGradient id="purpleGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#8B5CF6" />
                  <stop offset="100%" stopColor="#6D28D9" />
                </linearGradient>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8B5CF6" stopOpacity="0.5" />
                  <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {/* Area Fill */}
              <path d={area} fill="url(#areaGradient)" className="opacity-80" />

              {/* Main Line */}
              <path
                d={line}
                fill="none"
                stroke="url(#purpleGradient)"
                strokeWidth="4"
                strokeLinecap="round"
                className="chart-path filter drop-shadow-[0_4px_6px_rgba(139,92,246,0.5)]"
              />

              {/* Last point highlight */}
              {(() => {
                const pts = data.length
                const lx = VIEWPORT_WIDTH
                const ly =
                  PADDING_TOP +
                  (1 - (lastPoint.count - minCount) / range) * (VIEWPORT_HEIGHT - PADDING_TOP)
                return (
                  <circle
                    cx={lx}
                    cy={ly}
                    r="4"
                    fill="#8B5CF6"
                    stroke="#0F0A1E"
                    strokeWidth="2"
                    className="animate-pulse"
                  />
                )
              })()}
            </svg>

            {/* Tooltip on last node */}
            <div
              className="absolute right-0 -mt-10 -mr-4 glass-tooltip px-3 py-2 rounded-lg pointer-events-none z-20 shadow-xl"
              style={{ top: `${lastNormYPct}%` }}
            >
              <div className="text-[0.65rem] text-text-muted uppercase mb-1">
                {new Date(lastPoint.date).toLocaleDateString('pt-BR', {
                  weekday: 'short',
                  day: '2-digit',
                  month: 'short',
                })}
              </div>
              <div className="text-sm font-bold text-text-light flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-primary" />
                {lastPoint.count} Conversas
              </div>
            </div>
          </>
        )}

        {/* X Axis Labels */}
        <div className="absolute bottom-0 w-full flex justify-between text-[0.65rem] text-text-muted font-medium pt-2">
          {axisLabels.length > 0
            ? axisLabels.map((label, i) => <span key={i}>{label}</span>)
            : ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((d) => (
                <span key={d}>{d}</span>
              ))}
        </div>
      </div>
    </Card>
  )
}
