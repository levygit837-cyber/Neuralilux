import { 
  TrendUp, 
  TrendDown, 
  Chats, 
  PaperPlaneRight, 
  CheckCircle, 
  Star,
  StarHalf,
  ArrowUpRight
} from '@phosphor-icons/react'
import { Card } from '@/components/ui/Card'
import type { Metric } from '@/types/dashboard'

interface MetricCardProps {
  metric: Metric
  index?: number
}

export function MetricCard({ metric, index = 0 }: MetricCardProps) {
  const isPositive = metric.trend === 'up'
  const Icon = isPositive ? TrendUp : TrendDown
  
  // Map metric labels to icons
  const getIconForLabel = (label: string) => {
    if (label.toLowerCase().includes('conversa')) return Chats
    if (label.toLowerCase().includes('mensagem')) return PaperPlaneRight
    if (label.toLowerCase().includes('sucesso') || label.toLowerCase().includes('resposta')) return CheckCircle
    if (label.toLowerCase().includes('satisfação')) return Star
    return Star
  }
  
  const MetricIcon = getIconForLabel(metric.label)
  const delayClass = `delay-${(index % 5) * 100}` as const
  
  const isSatisfaction = metric.label.toLowerCase().includes('satisfação')
  const isSuccessRate = metric.label.toLowerCase().includes('sucesso') || metric.label.toLowerCase().includes('resposta')
  
  // Extract numeric value for progress bar
  const numericValue = typeof metric.value === 'string' ? parseFloat(metric.value.replace('%', '')) : 0

  return (
    <Card className={`relative overflow-hidden group hover:border-primary/40 transition-colors animate-slide-up ${delayClass}`}>
      {/* Decorative background icon */}
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        <MetricIcon weight="fill" className="text-6xl text-primary" />
      </div>
      
      {/* Neon glow for success rate */}
      {isSuccessRate && (
        <div className="absolute -top-10 -right-10 w-24 h-24 bg-primary/20 blur-2xl rounded-full pointer-events-none" />
      )}
      
      <h3 className="text-text-muted text-sm font-medium mb-4 flex items-center gap-2">
        <MetricIcon weight="regular" className="text-primary" />
        {metric.label}
      </h3>
      
      <div className="flex items-end justify-between relative z-10">
        <div className="text-3xl font-bold text-text-light tracking-tight">
          {metric.value}
        </div>
        
        {isSuccessRate ? (
          <div className="flex flex-col items-end">
            <div className="flex items-center text-success text-sm font-medium mb-0.5">
              <ArrowUpRight weight="regular" className="mr-1" /> 2.1%
            </div>
            <span className="text-[0.65rem] text-text-muted uppercase tracking-wide">
              Respostas Enviadas
            </span>
          </div>
        ) : (
          <div className="flex items-center text-success text-sm bg-success/10 px-2 py-1 rounded-md mb-1">
            <Icon weight="regular" className="mr-1 text-xs" />
            {metric.change}
          </div>
        )}
      </div>
      
      {/* Progress bar for success rate */}
      {isSuccessRate && (
        <div className="w-full bg-dark h-1.5 rounded-full mt-4 overflow-hidden">
          <div 
            className="bg-success h-full rounded-full transition-all duration-1000" 
            style={{ width: `${Math.min(numericValue, 100)}%` }}
          />
        </div>
      )}
      
      {/* Star rating for satisfaction */}
      {isSatisfaction && (
        <div className="flex gap-1 mt-4 text-warning text-sm">
          <Star weight="fill" />
          <Star weight="fill" />
          <Star weight="fill" />
          <Star weight="fill" />
          <StarHalf weight="fill" />
        </div>
      )}
    </Card>
  )
}
