import { TrendingUp, TrendingDown } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import type { Metric } from '@/types/dashboard'

interface MetricCardProps {
  metric: Metric
}

export function MetricCard({ metric }: MetricCardProps) {
  const isPositive = metric.trend === 'up'
  const Icon = isPositive ? TrendingUp : TrendingDown

  return (
    <Card className="flex flex-col gap-3">
      <p className="text-sm font-medium text-text-muted">{metric.label}</p>
      <p className="text-3xl font-bold text-text-light">{metric.value}</p>
      <div className="flex items-center gap-1">
        <Icon className={`h-4 w-4 ${isPositive ? 'text-success' : 'text-error'}`} />
        <span className={`text-sm font-medium ${isPositive ? 'text-success' : 'text-error'}`}>
          {metric.change}
        </span>
      </div>
    </Card>
  )
}
