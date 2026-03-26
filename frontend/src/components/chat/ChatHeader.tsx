import { Avatar } from '@/components/ui/Avatar'
import { MoreVertical, Phone } from 'lucide-react'

interface ChatHeaderProps {
  name: string
  avatar?: string
  status?: string
}

export function ChatHeader({ name, avatar, status }: ChatHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border-color bg-card px-6 py-4">
      <div className="flex items-center gap-4">
        <Avatar
          src={avatar}
          fallback={name.substring(0, 2).toUpperCase()}
          size="md"
        />
        <div>
          <h2 className="text-base font-semibold text-text-light">{name}</h2>
          {status && <p className="text-xs text-text-muted">{status}</p>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button className="flex h-10 w-10 items-center justify-center rounded-lg bg-hover text-text-gray transition-colors hover:bg-border">
          <Phone className="h-5 w-5" />
        </button>
        <button className="flex h-10 w-10 items-center justify-center rounded-lg bg-hover text-text-gray transition-colors hover:bg-border">
          <MoreVertical className="h-5 w-5" />
        </button>
      </div>
    </div>
  )
}
