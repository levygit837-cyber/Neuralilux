'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  SquaresFour, 
  ChatCircleDots, 
  Robot, 
  Package, 
  SlidersHorizontal,
  Brain,
  Sparkle,
  CaretUp
} from '@phosphor-icons/react'
import { ROUTES } from '@/lib/constants'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  {
    href: ROUTES.DASHBOARD,
    label: 'Dashboard',
    icon: SquaresFour,
    badge: null,
  },
  {
    href: ROUTES.CHAT,
    label: 'Chat',
    icon: ChatCircleDots,
    badge: '14',
  },
  {
    href: ROUTES.AGENT,
    label: 'Agentes IA',
    icon: Robot,
    badge: null,
  },
  {
    href: ROUTES.STOCK,
    label: 'Estoque',
    icon: Package,
    badge: null,
  },
]

const SETTINGS_ITEM = {
  href: ROUTES.SETTINGS,
  label: 'Configurações',
  icon: SlidersHorizontal,
}

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden w-72 flex-col border-r border-brand-border bg-brand-card/50 lg:flex relative z-20 shadow-panel backdrop-blur-sm">
      {/* Floating gradient glow behind sidebar */}
      <div className="absolute top-0 left-0 w-full h-64 bg-primary/5 rounded-full blur-[80px] pointer-events-none -z-10" />

      {/* Logo Area */}
      <div className="h-20 px-6 flex items-center border-b border-brand-border/50">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary shadow-glow">
            <Brain weight="fill" className="text-white text-lg" />
            {/* AI Sparkle absolute */}
            <Sparkle weight="fill" className="text-accent text-[10px] absolute -top-1 -right-1" />
          </div>
          <span className="font-bold tracking-[0.15em] text-sm uppercase bg-clip-text text-transparent bg-gradient-to-r from-content-light to-content-gray">
            NeuraliLux
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-8 space-y-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-4 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 group relative overflow-hidden',
                isActive
                  ? 'text-white bg-brand-hover border border-primary/20 shadow-[inset_4px_0_0_0_#8B5CF6]'
                  : 'text-content-muted hover:text-content-light hover:bg-brand-hover/50'
              )}
            >
              <Icon 
                weight={isActive ? 'fill' : 'regular'} 
                className={cn(
                  'text-xl',
                  isActive ? 'text-primary drop-shadow-[0_0_8px_rgba(139,92,246,0.6)]' : 'group-hover:text-primary transition-colors'
                )}
              />
              <span className="font-medium">{item.label}</span>
              {item.badge && (
                <span className="bg-primary text-[10px] font-bold px-2 py-0.5 rounded-full ml-auto">
                  {item.badge}
                </span>
              )}
            </Link>
          )
        })}

        {/* Settings separated with margin */}
        <Link
          href={SETTINGS_ITEM.href}
          className={cn(
            'flex items-center gap-4 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 group',
            pathname === SETTINGS_ITEM.href || pathname.startsWith(`${SETTINGS_ITEM.href}/`)
              ? 'text-white bg-brand-hover border border-primary/20 shadow-[inset_4px_0_0_0_#8B5CF6]'
              : 'text-content-muted hover:text-content-light hover:bg-brand-hover/50'
          )}
        >
          <SlidersHorizontal 
            weight={pathname === SETTINGS_ITEM.href || pathname.startsWith(`${SETTINGS_ITEM.href}/`) ? 'fill' : 'regular'} 
            className={cn(
              'text-xl',
              pathname === SETTINGS_ITEM.href || pathname.startsWith(`${SETTINGS_ITEM.href}/`)
                ? 'text-primary drop-shadow-[0_0_8px_rgba(139,92,246,0.6)]'
                : 'group-hover:text-primary transition-colors'
            )}
          />
          <span className="font-medium">{SETTINGS_ITEM.label}</span>
        </Link>
      </nav>

      {/* User Profile */}
      <div className="p-6 border-t border-brand-border/50 bg-brand-card/30">
        <div className="flex items-center gap-3 w-full p-2 rounded-xl hover:bg-brand-hover/50 transition-colors cursor-pointer border border-transparent hover:border-brand-border">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white font-bold border border-brand-border">
            IS
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold truncate text-content-light">Isabella Silva</p>
            <p className="text-xs text-content-muted truncate flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-status-success"></span> Workspace Pro
            </p>
          </div>
          <CaretUp weight="regular" className="text-content-muted" />
        </div>
      </div>
    </aside>
  )
}
