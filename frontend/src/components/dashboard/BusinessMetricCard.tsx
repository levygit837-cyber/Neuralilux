import { Card } from '@/components/ui/Card'
import type { BusinessMetric } from '@/types/dashboard'

interface BusinessMetricCardProps {
  businessMetric: BusinessMetric
}

export function BusinessMetricCard({ businessMetric }: BusinessMetricCardProps) {
  return (
    <Card className="flex flex-col gap-4">
      <h3 className="text-lg font-semibold text-text-light">{businessMetric.name}</h3>
      <div className="space-y-3">
        {businessMetric.metrics.map((metric, index) => (
          <div key={index} className="flex items-center justify-between">
            <span className="text-sm text-text-gray">{metric.label}</span>
            <span className="text-sm font-semibold text-text-light">{metric.value}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
