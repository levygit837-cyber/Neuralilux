'use client'

import { useAuthStore } from '@/stores/useAuthStore'
import { Brand } from './Brand'
import { NavList } from './NavList'

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join('')
}

export function Sidebar() {
  const user = useAuthStore((state) => state.user)
  const hasHydrated = useAuthStore((state) => state.hasHydrated)

  return (
    <aside className="relative z-20 hidden w-72 flex-col border-r border-brand-border bg-brand-card/50 shadow-panel backdrop-blur-sm lg:flex">
      <div className="pointer-events-none absolute left-0 top-0 -z-10 h-64 w-full rounded-full bg-primary/5 blur-[80px]" />

      <div className="flex h-20 items-center border-b border-brand-border/50 px-6">
        <Brand />
      </div>

      <NavList />

      {/* O cookie só é lido no cliente: até hidratar, reserva o espaço do bloco para não gerar mismatch de SSR nem salto de layout. */}
      {!hasHydrated ? (
        <div aria-hidden="true" className="h-[89px] border-t border-brand-border/50 bg-brand-card/30" />
      ) : (
        user && (
          <div className="border-t border-brand-border/50 bg-brand-card/30 p-6">
            <div className="flex w-full items-center gap-3 rounded-xl border border-transparent p-2">
              <div
                aria-hidden="true"
                className="flex h-10 w-10 items-center justify-center rounded-full border border-brand-border bg-gradient-to-br from-primary to-secondary font-bold text-white"
              >
                {initialsOf(user.name)}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-content-light">{user.name}</p>
                <p className="truncate text-xs text-content-muted">{user.email}</p>
              </div>
            </div>
          </div>
        )
      )}
    </aside>
  )
}
