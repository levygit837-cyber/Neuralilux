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
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-hover">
        <Icon className="h-5 w-5 text-primary-light" />
      </div>
      <div className="flex-1">
        <p className="text-sm font-medium text-content-light">{activity.title}</p>
        <p className="text-xs text-content-muted">{activity.description}</p>
      </div>
      <span className="text-xs text-content-muted">{activity.timestamp}</span>
    </div>
  )
}
