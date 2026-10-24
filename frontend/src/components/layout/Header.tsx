import { CalendarBlank } from '@phosphor-icons/react'

interface HeaderProps {
  title?: string
  showOnlineBadge?: boolean
}

export function Header({ title, showOnlineBadge = true }: HeaderProps) {
  const today = new Date().toLocaleDateString('pt-BR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })

  return (
    <header className="h-20 border-b border-brand-border/50 bg-brand-base/80 backdrop-blur-xl flex items-center justify-between px-4 sm:px-8 sticky top-0 z-10">
      <div>
        <h1 className="text-2xl font-semibold text-content-light tracking-tight flex items-center gap-2">
          {title || 'Dashboard'}
          {showOnlineBadge && (
            <span className="text-xs font-normal px-2 py-1 bg-status-success/10 text-status-success rounded border border-status-success/20 ml-2">
              Online
            </span>
          )}
        </h1>
      </div>
      
      <div className="flex items-center gap-4">
        {/* Date Picker */}
        <div className="hidden md:flex items-center gap-2 bg-brand-card border border-brand-border rounded-lg px-3 py-1.5 text-sm">
          <CalendarBlank weight="regular" className="text-content-muted" />
          <span>Hoje: {today}</span>
        </div>
      </div>
    </header>
  )
}
