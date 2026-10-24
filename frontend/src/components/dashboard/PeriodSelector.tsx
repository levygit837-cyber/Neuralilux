import { cn } from '@/lib/utils'
import type { DashboardPeriod } from '@/types/dashboard'

const PERIODS: { value: DashboardPeriod; label: string }[] = [
  { value: '7d', label: '7 dias' },
  { value: '30d', label: '30 dias' },
  { value: '90d', label: '90 dias' },
]

interface PeriodSelectorProps {
  period: DashboardPeriod
  onChange: (period: DashboardPeriod) => void
}

/** O período vale para o dashboard inteiro: todo número é "dos últimos N dias" contra os N dias antes. */
export function PeriodSelector({ period, onChange }: PeriodSelectorProps) {
  return (
    <div className="flex rounded-md border border-brand-border bg-brand-base p-1" role="group" aria-label="Período">
      {PERIODS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={period === option.value}
          onClick={() => onChange(option.value)}
          className={cn(
            'rounded px-3 py-1 text-xs font-medium transition',
            period === option.value
              ? 'border border-brand-border bg-brand-card text-content-light shadow-sm'
              : 'text-content-muted hover:text-content-light'
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
