import { MobileNav } from '@/components/layout/MobileNav'
import { QueryProvider } from '@/components/providers/QueryProvider'
import { RouteHeader } from '@/components/layout/RouteHeader'
import { Sidebar } from '@/components/layout/Sidebar'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <div className="flex h-dvh overflow-hidden bg-brand-base">
        <Sidebar />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <MobileNav />
          <RouteHeader />
          <main className="flex min-h-0 flex-1 flex-col overflow-auto">{children}</main>
        </div>
      </div>
    </QueryProvider>
  )
}
