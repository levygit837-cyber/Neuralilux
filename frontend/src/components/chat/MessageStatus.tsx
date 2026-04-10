import { Clock, Check } from '@phosphor-icons/react'
import type { MessageStatus as MessageStatusType } from '@/types/chat'

interface MessageStatusProps {
  status: MessageStatusType
}

export function MessageStatus({ status }: MessageStatusProps) {
  switch (status) {
    case 'pending':
      return <Clock weight="regular" className="text-sm text-content-muted" />
    case 'sending':
      return <Check weight="regular" className="text-sm text-content-muted" />
    case 'sent':
      return <Check weight="regular" className="text-sm text-content-muted" />
    case 'delivered':
      return <Check weight="fill" className="text-sm text-content-muted" />
    case 'read':
      return <Check weight="fill" className="text-sm text-blue-400" />
    default:
      return null
  }
}
