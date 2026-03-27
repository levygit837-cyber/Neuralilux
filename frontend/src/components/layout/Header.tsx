import { Bell } from 'lucide-react'
import { Avatar } from '@/components/ui/Avatar'

interface HeaderProps {
  title?: string
}

export function Header({ title }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border-color bg-card px-8 py-4">
      <div className="flex items-center gap-4">
        {title && <h1 className="text-xl font-bold text-text-light">{title}</h1>}
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
