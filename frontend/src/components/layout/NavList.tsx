'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { ROUTES } from '@/lib/constants'
import { cn } from '@/lib/utils'
import { useChatStore } from '@/stores/useChatStore'
import { NAV_ITEMS } from './navItems'

interface NavListProps {
  onNavigate?: () => void
}

export function NavList({ onNavigate }: NavListProps) {
  const pathname = usePathname()
  // Só se conhece depois que o chat carregou; antes disso não há selo.
  const unreadMessages = useChatStore((state) => state.counts?.unreadMessages ?? 0)

  return (
    <nav aria-label="Principal" className="flex-1 space-y-2 px-4 py-8">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon
        const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`)
        const unread = item.href === ROUTES.CHAT && unreadMessages > 0 ? String(unreadMessages) : null

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={isActive ? 'page' : undefined}
            className={cn(
              'group relative flex items-center gap-4 overflow-hidden rounded-xl px-4 py-3 text-sm font-medium transition-all duration-200',
              isActive
                ? 'border border-primary/20 bg-brand-hover text-white shadow-active-bar'
                : 'text-content-muted hover:bg-brand-hover/50 hover:text-content-light'
            )}
          >
            <Icon
              weight={isActive ? 'fill' : 'regular'}
              className={cn(
                'text-xl',
                isActive
                  ? 'text-primary-light drop-shadow-[0_0_8px_rgb(var(--color-primary)/0.6)]'
                  : 'transition-colors group-hover:text-primary-light'
              )}
            />
            <span className="font-medium">{item.label}</span>
            {unread && (
              <span className="ml-auto rounded-full bg-primary px-2 py-0.5 text-[10px] font-bold">
                <span aria-hidden="true">{unread}</span>
                <span className="sr-only">{unread} mensagens não lidas</span>
              </span>
            )}
          </Link>
        )
      })}
    </nav>
  )
}
