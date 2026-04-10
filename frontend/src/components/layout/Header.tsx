import { Bell, MagnifyingGlass, CalendarBlank, CaretDown } from '@phosphor-icons/react'
import { Avatar } from '@/components/ui/Avatar'

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
    <header className="h-20 border-b border-border-color/50 bg-dark/80 backdrop-blur-xl flex items-center justify-between px-8 sticky top-0 z-10">
      <div>
        <h1 className="text-2xl font-semibold text-text-light tracking-tight flex items-center gap-2">
          {title || 'Dashboard'}
          {showOnlineBadge && (
            <span className="text-xs font-normal px-2 py-1 bg-success/10 text-success rounded border border-success/20 ml-2">
              Online
            </span>
          )}
        </h1>
      </div>
      
      <div className="flex items-center gap-4">
        {/* Date Picker */}
        <div className="hidden md:flex items-center gap-2 bg-card border border-border-color rounded-lg px-3 py-1.5 text-sm cursor-pointer hover:border-primary/50 transition-colors">
          <CalendarBlank weight="regular" className="text-text-muted" />
          <span>Hoje: {today}</span>
          <CaretDown weight="regular" className="text-text-muted ml-2" />
        </div>
        
        {/* Utilities */}
        <div className="flex items-center gap-2 border-l border-border-color pl-4">
          <button className="w-9 h-9 rounded bg-card border border-border-color flex items-center justify-center hover:text-primary hover:border-primary transition-all relative">
            <Bell weight="regular" className="text-lg" />
            <span className="absolute top-2 right-2 w-2 h-2 bg-accent rounded-full animate-pulse-slow"></span>
          </button>
          <button className="w-9 h-9 rounded bg-card border border-border-color flex items-center justify-center hover:text-primary hover:border-primary transition-all">
            <MagnifyingGlass weight="regular" className="text-lg" />
          </button>
        </div>
      </div>
    </header>
  )
}
