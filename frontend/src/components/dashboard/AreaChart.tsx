'use client'

import { Card } from '@/components/ui/Card'
import { Target } from '@phosphor-icons/react'
import type { SatisfactionMetrics } from '@/types/dashboard'

interface AreaChartProps {
  metrics: SatisfactionMetrics
  isLoading?: boolean
  className?: string
}

const VIEWPORT_WIDTH = 600
const VIEWPORT_HEIGHT = 160
const SCORE_MIN = 1
const SCORE_MAX = 5

function scoreToY(score: number): number {
  const normalized = (score - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)
  return VIEWPORT_HEIGHT - normalized * VIEWPORT_HEIGHT
}

function buildSvgPaths(history: SatisfactionMetrics['history']): { line: string; area: string } {
  if (history.length === 0) return { line: '', area: '' }
  if (history.length === 1) {
    const y = scoreToY(history[0].score)
    return {
      line: `M0,${y} L${VIEWPORT_WIDTH},${y}`,
      area: `M0,${y} L${VIEWPORT_WIDTH},${y} L${VIEWPORT_WIDTH},${VIEWPORT_HEIGHT} L0,${VIEWPORT_HEIGHT} Z`,
    }
  }

  const points = history.map((h, i) => ({
    x: (i / (history.length - 1)) * VIEWPORT_WIDTH,
    y: scoreToY(h.score),
  }))

  let line = `M${points[0].x},${points[0].y}`
  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1]
    const curr = points[i]
    const cpx = (prev.x + curr.x) / 2
    line += ` C${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`
  }

  const last = points[points.length - 1]
  const area = `${line} L${last.x},${VIEWPORT_HEIGHT} L0,${VIEWPORT_HEIGHT} Z`

  return { line, area }
}

function formatMonth(month: string): string {
  const [year, m] = month.split('-')
  const date = new Date(Number(year), Number(m) - 1, 1)
  return date.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '')
}

export function AreaChart({ metrics, isLoading, className }: AreaChartProps) {
  const { line, area } = buildSvgPaths(metrics.history)
  const targetY = scoreToY(metrics.target_score)

  const yLabels = ['5.0', '4.5', '4.0', '3.5', '3.0']

  return (
    <Card
      className={`flex flex-col h-[380px] animate-slide-up delay-500 relative overflow-hidden group ${className}`}
    >
      {/* Decorative background element */}
      <div className="absolute -bottom-20 -left-20 w-64 h-64 bg-accent/5 rounded-full blur-3xl pointer-events-none" />

      <div className="flex justify-between items-start mb-6 relative z-10">
        <div>
          <h3 className="font-medium text-text-light">Satisfação (CSAT)</h3>
          <p className="text-xs text-text-muted mt-1">Evolução do score por semestre</p>
        </div>
        <div className="text-xs px-2 py-1 bg-accent/10 text-accent rounded border border-accent/20 flex items-center gap-1 font-medium">
          <Target weight="regular" /> Meta: {metrics.target_score}
        </div>
      </div>

      <div className="flex-1 relative w-full mt-4 flex flex-col justify-end">
        {/* Y Axis Markers */}
        <div className="absolute left-0 inset-y-0 w-6 flex flex-col justify-between text-[0.6rem] text-text-muted font-medium pb-6 z-10">
          {yLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>

        <div className="ml-8 relative h-full">
          {isLoading ? (
            <div className="flex items-center justify-center h-full pb-6">
              <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin" />
            </div>
          ) : metrics.history.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full pb-6 gap-2">
              <Target weight="thin" className="text-accent/40 text-4xl" />
              <p className="text-xs text-text-muted">Sem avaliações registradas ainda</p>
              <p className="text-[0.65rem] text-text-muted/60">
                As avaliações aparecerão aqui assim que os clientes responderem
              </p>
            </div>
          ) : (
            <>
              <svg
                viewBox={`0 0 ${VIEWPORT_WIDTH} ${VIEWPORT_HEIGHT}`}
                className="w-full h-full preserve-3d overflow-visible"
              >
                <defs>
                  <linearGradient id="pinkGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#EC4899" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#EC4899" stopOpacity="0.0" />
                  </linearGradient>
                </defs>

                {/* Target Line (Dotted) */}
                <line
                  x1="0"
                  y1={targetY}
                  x2={VIEWPORT_WIDTH}
                  y2={targetY}
                  stroke="#EC4899"
                  strokeWidth="1"
                  strokeDasharray="4 4"
                  className="opacity-50"
                />

                {/* Pink Area Fill */}
                <path
                  d={area}
                  fill="url(#pinkGradient)"
                  className="opacity-70 group-hover:opacity-100 transition-opacity duration-700"
                />

                {/* Line */}
                <path
                  d={line}
                  fill="none"
                  stroke="#EC4899"
                  strokeWidth="3"
                  strokeLinecap="round"
                  className="chart-path filter drop-shadow-[0_2px_4px_rgba(236,72,153,0.4)]"
                />

                {/* Nodes */}
                {metrics.history.map((h, i) => {
                  const x = (i / (metrics.history.length - 1)) * VIEWPORT_WIDTH
                  const y = scoreToY(h.score)
                  const isLast = i === metrics.history.length - 1
                  return (
                    <circle
                      key={h.month}
                      cx={x}
                      cy={y}
                      r={isLast ? 4 : 3}
                      fill={isLast ? '#EC4899' : '#0F0A1E'}
                      stroke="#EC4899"
                      strokeWidth="2"
                      className={
                        isLast
                          ? 'shadow-[0_0_10px_rgba(236,72,153,0.8)]'
                          : ''
                      }
                    />
                  )
                })}
              </svg>

              {/* X Axis Labels */}
              <div className="absolute bottom-0 w-full flex justify-between text-[0.65rem] text-text-muted font-medium pt-2">
                {metrics.history.map((h) => (
                  <span key={h.month}>{formatMonth(h.month)}</span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Current score badge */}
      {!isLoading && metrics.current_score > 0 && (
        <div className="mt-4 pt-3 border-t border-border-color/50 flex items-center justify-between relative z-10">
          <span className="text-xs text-text-muted">Score atual</span>
          <span className="text-sm font-bold text-accent">{metrics.current_score} / 5.0</span>
        </div>
      )}
    </Card>
  )
}
