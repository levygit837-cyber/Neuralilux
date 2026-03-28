'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Bot, MessageSquare, LayoutDashboard, Settings, Boxes } from 'lucide-react'
import { ROUTES } from '@/lib/constants'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  {
    href: ROUTES.DASHBOARD,
    label: 'Dashboard',
    icon: LayoutDashboard,
  },
  {
    href: ROUTES.CHAT,
    label: 'Chat',
    icon: MessageSquare,
  },
  {
    href: ROUTES.AGENT,
    label: 'Agente',
    icon: Bot,
  },
  {
    href: ROUTES.STOCK,
    label: 'Estoque',
    icon: Boxes,
  },
  {
    href: ROUTES.SETTINGS,
    label: 'Configurações',
    icon: Settings,
  },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="hidden w-72 flex-col border-r border-border-color bg-card lg:flex">
      <div className="border-b border-border-color px-6 py-6">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-primary/80">
          NeuraliLux
        </p>
      </div>

      <nav className="flex-1 space-y-2 p-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-white'
                  : 'text-text-gray hover:bg-hover hover:text-text-light'
              )}
            >
              <Icon className="h-5 w-5" />
              <span>{item.label}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
