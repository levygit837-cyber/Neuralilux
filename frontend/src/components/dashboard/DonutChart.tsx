'use client'

import { Card } from '@/components/ui/Card'
import type { ResolutionMetrics } from '@/types/dashboard'

interface DonutChartProps {
  data: ResolutionMetrics
  isLoading?: boolean
  className?: string
}

interface SegmentConfig {
  label: string
  color: string
  key: keyof ResolutionMetrics
}

const SEGMENTS: SegmentConfig[] = [
  { label: 'Resolvidas', color: '#10B981', key: 'resolved' },
  { label: 'Pendentes',  color: '#F59E0B', key: 'pending' },
  { label: 'Escaladas',  color: '#EC4899', key: 'escalated' },
]

const RADIUS = 40
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function DonutChart({ data, isLoading, className }: DonutChartProps) {
  const total = data.resolved + data.pending + data.escalated || 1

  const segments = SEGMENTS.map((seg) => ({
    ...seg,
    value: data[seg.key],
    percentage: Math.round((data[seg.key] / total) * 100),
  }))

  let currentOffset = 0

  return (
    <Card className={`flex flex-col h-[380px] animate-slide-up delay-500 ${className}`}>
      <div className="mb-2">
        <h3 className="font-medium text-text-light">Taxa de Resolução</h3>
        <p className="text-xs text-text-muted mt-1">Status final dos chamados da IA</p>
      </div>

      <div className="flex-1 flex items-center justify-center relative">
        {isLoading ? (
          <div className="w-8 h-8 rounded-full border-2 border-primary border-t-transparent animate-spin" />
        ) : (
          <>
            {/* SVG Donut */}
            <svg width="220" height="220" viewBox="0 0 100 100" className="transform -rotate-90">
              {/* Background Track */}
              <circle cx="50" cy="50" r={RADIUS} fill="none" stroke="#2D2447" strokeWidth="10" />

              {/* Segments */}
              {segments.map((segment) => {
                const segmentLength = (segment.percentage / 100) * CIRCUMFERENCE
                const dashArray = `${segmentLength} ${CIRCUMFERENCE}`
                const dashOffset = -currentOffset

                currentOffset += segmentLength

                return (
                  <circle
                    key={segment.label}
                    cx="50"
                    cy="50"
                    r={RADIUS}
                    fill="none"
                    stroke={segment.color}
                    strokeWidth="10"
                    strokeDasharray={dashArray}
                    strokeDashoffset={dashOffset}
                    className="donut-segment"
                  />
                )
              })}
            </svg>

            {/* Inner Content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-3xl font-bold text-text-light">
                {segments[0].percentage}
                <span className="text-lg text-text-muted">%</span>
              </span>
              <span className="text-[0.65rem] text-success uppercase tracking-wider font-semibold mt-1">
                Resolvidas
              </span>
            </div>
          </>
        )}
      </div>

      {/* Legend */}
      <div className="flex justify-center gap-6 mt-4 pt-4 border-t border-border-color/50">
        {segments.map((segment) => (
          <div
            key={segment.label}
            className="flex items-center gap-2 group cursor-pointer hover:-translate-y-1 transition-transform"
          >
            <span
              className="w-3 h-3 rounded-full border border-dark"
              style={{
                backgroundColor: segment.color,
                boxShadow: `0 0 8px ${segment.color}66`,
              }}
            />
            <span className="text-xs text-text-muted group-hover:text-text-light transition">
              {segment.label}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}
