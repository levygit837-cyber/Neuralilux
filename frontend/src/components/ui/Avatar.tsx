import * as React from 'react'
import { cn } from '@/lib/utils'
import { AvatarImage } from '@/components/ui/AvatarImage'

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string
  alt?: string
  fallback?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-12 w-12 text-base',
  lg: 'h-16 w-16 text-xl',
}

const avatarSizes = {
  sm: '32px',
  md: '48px',
  lg: '64px',
}

const Avatar = React.forwardRef<HTMLDivElement, AvatarProps>(
  ({ className, src, alt, fallback, size = 'md', ...props }, ref) => {
    const [imageError, setImageError] = React.useState(false)

    return (
      <div
        ref={ref}
        className={cn(
          'relative flex shrink-0 overflow-hidden rounded-full bg-gradient-to-br from-primary to-primary-dark',
          sizeClasses[size],
          className
        )}
        {...props}
      >
        {src && !imageError ? (
          <AvatarImage
            src={src}
            alt={alt || 'Avatar'}
            sizes={avatarSizes[size]}
            className="object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-white font-semibold">
            {fallback || '?'}
          </div>
        )}
      </div>
    )
  }
)
Avatar.displayName = 'Avatar'

export { Avatar }
