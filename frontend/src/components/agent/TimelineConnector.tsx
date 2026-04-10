'use client'

interface TimelineConnectorProps {
  variant?: 'through' | 'bottom-gradient'
  topOffset?: string
  bottomOffset?: string
}

export function TimelineConnector({
  variant = 'through',
  topOffset = '0',
  bottomOffset = '-32px',
}: TimelineConnectorProps) {
  if (variant === 'bottom-gradient') {
    return (
      <div
        className="absolute left-6 w-px z-0 bg-gradient-to-b from-border-color to-transparent"
        style={{ top: `-32px`, bottom: '16px' }}
      />
    )
  }

  return (
    <div
      className="absolute left-6 w-px bg-border-color z-0"
      style={{ top: topOffset, bottom: bottomOffset }}
    />
  )
}
