import { 
  TrendUp, 
  TrendDown, 
  Chats, 
  PaperPlaneRight, 
  CheckCircle, 
  Star,
  StarHalf
} from '@phosphor-icons/react'
import type { IconWeight } from '@phosphor-icons/react'
import { Card } from '@/components/ui/Card'
import type { Metric } from '@/types/dashboard'

interface MetricCardProps {
  metric: Metric
  index?: number
}

function MetricIcon({ label, weight, className }: { label: string; weight: IconWeight; className?: string }) {
  const normalized = label.toLowerCase()
  if (normalized.includes('conversa')) return <Chats weight={weight} className={className} />
  if (normalized.includes('mensagem')) return <PaperPlaneRight weight={weight} className={className} />
  if (normalized.includes('sucesso') || normalized.includes('resposta')) return <CheckCircle weight={weight} className={className} />
  return <Star weight={weight} className={className} />
}

export function MetricCard({ metric, index = 0 }: MetricCardProps) {
  const isPositive = metric.trend === 'up'
  const Icon = isPositive ? TrendUp : TrendDown
  
  const delayClass = `delay-${(index % 5) * 100}` as const
  
  const isSatisfaction = metric.label.toLowerCase().includes('satisfação')
  const isSuccessRate = metric.label.toLowerCase().includes('sucesso') || metric.label.toLowerCase().includes('resposta')
  
  // Extract numeric value for progress bar and star rating
  const numericValue = typeof metric.value === 'string' ? parseFloat(metric.value.replace('%', '')) : 0
  const rating = typeof metric.value === 'number' ? metric.value : numericValue

  return (
    <Card className={`relative overflow-hidden group hover:border-primary/40 transition-colors animate-slide-up ${delayClass}`}>
      {/* Decorative background icon */}
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        <MetricIcon label={metric.label} weight="fill" className="text-6xl text-primary-light" />
      </div>
      
      {/* Neon glow for success rate */}
      {isSuccessRate && (
        <div className="absolute -top-10 -right-10 w-24 h-24 bg-primary/20 blur-2xl rounded-full pointer-events-none" />
      )}
      
      <h3 className="text-content-muted text-sm font-medium mb-4 flex items-center gap-2">
        <MetricIcon label={metric.label} weight="regular" className="text-primary-light" />
        {metric.label}
      </h3>
      
      <div className="flex items-end justify-between relative z-10">
        <div className="text-3xl font-bold text-content-light tracking-tight">
          {metric.value}
        </div>
        
        {isSuccessRate ? (
          <span className="text-[0.65rem] text-content-muted uppercase tracking-wide">
            {metric.change}
          </span>
        ) : (
          <div className="flex items-center text-status-success text-sm bg-status-success/10 px-2 py-1 rounded-md mb-1">
            <Icon weight="regular" className="mr-1 text-xs" />
            {metric.change}
          </div>
        )}
      </div>
      
      {/* Progress bar for success rate */}
      {isSuccessRate && (
        <div className="w-full bg-brand-base h-1.5 rounded-full mt-4 overflow-hidden">
          <div 
            className="bg-status-success h-full rounded-full transition-all duration-1000" 
            style={{ width: `${Math.min(numericValue, 100)}%` }}
          />
        </div>
      )}
      
      {/* Estrelas só com nota real (valor numérico > 0); sem avaliação, nada de estrela */}
      {isSatisfaction && Number.isFinite(rating) && rating > 0 && (
        <div role="img" aria-label={`Nota ${rating} de 5`} className="flex gap-1 mt-4 text-status-warning text-sm">
          {[1, 2, 3, 4, 5].map((position) =>
            rating >= position ? (
              <Star key={position} weight="fill" aria-hidden="true" />
            ) : rating >= position - 0.5 ? (
              <StarHalf key={position} weight="fill" aria-hidden="true" />
            ) : (
              <Star key={position} weight="regular" aria-hidden="true" />
            )
          )}
        </div>
      )}
    </Card>
  )
}
