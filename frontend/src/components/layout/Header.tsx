import { Zap, Bell, LayoutDashboard, Smartphone, MessageSquare, QrCode } from 'lucide-react'
import Link from 'next/link'
import { Avatar } from '@/components/ui/Avatar'
import { ROUTES } from '@/lib/constants'

const navItems = [
  { href: ROUTES.INSTANCES, label: 'Instâncias', icon: Smartphone },
  { href: ROUTES.DASHBOARD, label: 'Dashboard', icon: LayoutDashboard },
  { href: ROUTES.CHAT, label: 'Chat', icon: MessageSquare },
  { href: ROUTES.QR, label: 'QR Code', icon: QrCode },
]

export function Header() {
  return (
    <header className="flex items-center justify-between border-b border-border-color bg-card px-8 py-6">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
            <Zap className="h-6 w-6 text-text-light" />
          </div>
          <h1 className="text-2xl font-bold text-text-light">Neuralilux</h1>
        </div>
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-text-gray transition-colors hover:bg-hover hover:text-text-light"
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            )
          })}
        </nav>
      </div>
      <div className="flex items-center gap-4">
        <button className="flex h-10 w-10 items-center justify-center rounded-lg bg-hover text-text-gray transition-colors hover:bg-border">
          <Bell className="h-5 w-5" />
        </button>
        <Avatar fallback="U" size="md" />
      </div>
    </header>
  )
}
