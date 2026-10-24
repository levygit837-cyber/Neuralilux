import { TrendUp, TrendDown, Minus } from '@phosphor-icons/react'
import type { Icon } from '@phosphor-icons/react'
import { Card } from '@/components/ui/Card'
import { WidgetError } from '@/components/dashboard/WidgetError'
import type { Trend } from '@/lib/dashboardTrend'
import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  icon: Icon
  /** `undefined` enquanto carrega. */
  value?: string
  caption?: string
  /** Tendência contra o período anterior; `null` quando não há base de comparação. */
  trend?: Trend | null
  /** 0 a 100; mostra a barra de progresso (taxas). */
  progress?: number | null
  error?: string | null
  onRetry: () => void
  index?: number
}

const TREND_ICON = { up: TrendUp, down: TrendDown, flat: Minus } as const
const TREND_COLOR = {
  up: 'bg-status-success/10 text-status-success',
  down: 'bg-status-error/10 text-status-error',
  flat: 'bg-brand-hover text-content-muted',
} as const

export function MetricCard({ label, icon: MetricIcon, value, caption, trend, progress, error, onRetry, index = 0 }: MetricCardProps) {
  const delayClass = `delay-${(index % 5) * 100}`

  if (error) {
    return (
      <Card className="min-h-40">
        <h3 className="mb-3 text-sm font-medium text-content-muted">{label}</h3>
        <WidgetError message={error} onRetry={onRetry} />
      </Card>
    )
  }

  if (value === undefined) {
    return <div className="h-40 animate-pulse rounded-lg bg-brand-card" aria-busy="true" aria-label={`Carregando ${label}`} />
  }

  const TrendIcon = trend ? TREND_ICON[trend.direction] : null

  return (
    <Card className={cn('group relative animate-slide-up overflow-hidden transition-colors hover:border-primary/40', delayClass)}>
      <div className="absolute right-0 top-0 p-4 opacity-10 transition-opacity group-hover:opacity-20">
        <MetricIcon weight="fill" className="text-6xl text-primary-light" aria-hidden="true" />
      </div>

      <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-content-muted">
        <MetricIcon weight="regular" className="text-primary-light" aria-hidden="true" />
        {label}
      </h3>

      <div className="relative z-10 flex items-end justify-between">
        <div className="text-3xl font-bold tracking-tight text-content-light">{value}</div>
        {trend && TrendIcon && (
          <div
            className={cn('mb-1 flex items-center rounded-md px-2 py-1 text-sm', TREND_COLOR[trend.direction])}
            title="Contra o período anterior"
          >
            <TrendIcon weight="regular" className="mr-1 text-xs" aria-hidden="true" />
            {trend.label}
          </div>
        )}
      </div>

      {caption && <p className="relative z-10 mt-2 text-xs text-content-muted">{caption}</p>}

      {progress !== undefined && progress !== null && (
        <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-brand-base">
          <div
            className="h-full rounded-full bg-status-success transition-all duration-1000"
            style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
          />
        </div>
      )}
    </Card>
  )
}
