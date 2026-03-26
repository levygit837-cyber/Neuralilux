import { Zap, Bell } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'

export function Header() {
  return (
    <header className="flex items-center justify-between border-b border-border-color bg-card px-8 py-6">
      <div className="flex items-center gap-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
          <Zap className="h-6 w-6 text-text-light" />
        </div>
        <h1 className="text-2xl font-bold text-text-light">Neuralilux</h1>
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
