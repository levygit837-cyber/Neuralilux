import * as React from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  count?: number
  variant?: 'default' | 'success' | 'warning' | 'error'
}

const variantClasses = {
  default: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning-yellow',
  error: 'bg-error',
}

const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, count, variant = 'default', ...props }, ref) => {
    if (!count || count === 0) return null

    return (
      <div
        ref={ref}
        className={cn(
          'flex h-6 min-w-[24px] items-center justify-center rounded-full px-2 text-xs font-semibold text-text-light',
          variantClasses[variant],
          className
        )}
        {...props}
      >
        {count > 99 ? '99+' : count}
      </div>
    )
  }
)
Badge.displayName = 'Badge'

export { Badge }
