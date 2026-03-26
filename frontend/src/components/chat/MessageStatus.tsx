import { Clock, Check, CheckCheck } from 'lucide-react'
import type { MessageStatus as MessageStatusType } from '@/types/chat'

interface MessageStatusProps {
  status: MessageStatusType
}

export function MessageStatus({ status }: MessageStatusProps) {
  switch (status) {
    case 'pending':
      return <Clock className="h-4 w-4 text-text-muted" />
    case 'sending':
      return <Check className="h-4 w-4 text-text-muted" />
    case 'sent':
      return <CheckCheck className="h-4 w-4 text-text-muted" />
    case 'delivered':
      return <CheckCheck className="h-4 w-4 text-text-muted" />
    case 'read':
      return <CheckCheck className="h-4 w-4 text-primary" />
    default:
      return null
  }
}
