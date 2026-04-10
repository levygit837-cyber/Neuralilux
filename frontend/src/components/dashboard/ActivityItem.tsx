import { MessageSquare, Calendar, ShoppingBag } from 'lucide-react'
import type { Activity } from '@/types/dashboard'

interface ActivityItemProps {
  activity: Activity
}

const iconMap = {
  message: MessageSquare,
  appointment: Calendar,
  sale: ShoppingBag,
}

export function ActivityItem({ activity }: ActivityItemProps) {
  const Icon = activity.type ? iconMap[activity.type] : MessageSquare

  return (
    <div className="flex items-center gap-4 py-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-hover">
        <Icon className="h-5 w-5 text-primary" />
      </div>
      <div className="flex-1">
        <p className="text-sm font-medium text-text-light">{activity.title}</p>
        <p className="text-xs text-text-muted">{activity.description}</p>
      </div>
      <span className="text-xs text-text-muted">{activity.timestamp}</span>
    </div>
  )
}
