'use client'

import { Card } from '@/components/ui/Card'
import { WhatsappLogo, Globe, InstagramLogo, ShareNetwork } from '@phosphor-icons/react'
import type { ChannelData } from '@/types/dashboard'

interface BarChartProps {
  channels: ChannelData[]
  isLoading?: boolean
  className?: string
}

const CHANNEL_CONFIG = [
  {
    name: 'WhatsApp',
    color: 'bg-success',
    icon: <WhatsappLogo weight="fill" className="text-success text-xl" />,
  },
  {
    name: 'Website',
    color: 'bg-primary',
    icon: <Globe weight="regular" className="text-primary text-xl" />,
  },
  {
    name: 'Instagram',
    color: 'bg-accent',
    icon: <InstagramLogo weight="fill" className="text-accent text-xl" />,
  },
]

function formatCount(count: number): string {
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`
  return count.toString()
}

export function BarChart({ channels, isLoading, className }: BarChartProps) {
  const maxCount = Math.max(...channels.map((c) => c.count), 1)

  // Merge real data with display config — always show 3 bars
  const bars = CHANNEL_CONFIG.map((config, i) => {
    const data = channels[i]
    return {
      ...config,
      count: data?.count ?? 0,
      heightPct: data ? Math.max(((data.count / maxCount) * 100), 4) : 4,
    }
  })

  return (
    <Card className={`flex flex-col h-[380px] animate-slide-up delay-400 ${className}`}>
      <div className="flex justify-between items-start mb-8">
        <div>
          <h3 className="font-medium text-text-light">Mensagens por Canal</h3>
          <p className="text-xs text-text-muted mt-1">Distribuição de envios omnicanal</p>
        </div>
        <div className="p-2 rounded bg-dark/50 text-primary">
          <ShareNetwork weight="regular" className="text-xl" />
        </div>
      </div>

      {isLoading ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        </div>
      ) : (
        <div className="flex-1 flex items-end justify-between gap-12 px-8 pb-6 relative z-10 border-b border-border-color/60">
          {bars.map((bar) => (
            <div
              key={bar.name}
              className="flex flex-col items-center flex-1 group chart-bar-group cursor-pointer"
            >
              <div className="w-full flex items-end justify-center h-48 relative">
                <div className="absolute -top-8 opacity-0 group-hover:opacity-100 transition-opacity text-xs font-bold text-text-light bg-dark px-2 py-1 rounded border border-border-color z-20">
                  {formatCount(bar.count)}
                </div>
                <div
                  className={`w-full max-w-[48px] ${bar.color} bar-fill rounded-t-md relative overflow-hidden transition-all duration-700`}
                  style={{ height: `${bar.heightPct}%` }}
                >
                  {/* Gradient overlay on bar */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
                </div>
              </div>
              <div className="mt-4 flex flex-col items-center gap-1">
                {bar.icon}
                <span className="text-xs font-medium text-text-muted">{bar.name}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
