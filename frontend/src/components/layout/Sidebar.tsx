import { Brand } from './Brand'
import { NavList } from './NavList'

export function Sidebar() {
  return (
    <aside className="relative z-20 hidden w-72 flex-col border-r border-brand-border bg-brand-card/50 shadow-panel backdrop-blur-sm lg:flex">
      <div className="pointer-events-none absolute left-0 top-0 -z-10 h-64 w-full rounded-full bg-primary/5 blur-[80px]" />

      <div className="flex h-20 items-center border-b border-brand-border/50 px-6">
        <Brand />
      </div>

      <NavList />

      <div className="border-t border-brand-border/50 bg-brand-card/30 p-6">
        <div className="flex w-full items-center gap-3 rounded-xl border border-transparent p-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-brand-border bg-gradient-to-br from-primary to-secondary font-bold text-white">
            IS
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-content-light">Isabella Silva</p>
            <p className="flex items-center gap-1 truncate text-xs text-content-muted">
              <span className="h-1.5 w-1.5 rounded-full bg-status-success"></span> Workspace Pro
            </p>
          </div>
        </div>
      </div>
    </aside>
  )
}
