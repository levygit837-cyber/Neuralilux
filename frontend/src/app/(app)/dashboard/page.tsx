'use client'

import { useState } from 'react'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { LineChart } from '@/components/dashboard/LineChart'
import { BarChart } from '@/components/dashboard/BarChart'
import { DonutChart } from '@/components/dashboard/DonutChart'
import { AreaChart } from '@/components/dashboard/AreaChart'
import { useDashboardData, type DashboardPeriod } from '@/hooks/useDashboardData'
import type {
  Metric,
  ResolutionMetrics,
  SatisfactionMetrics,
} from '@/types/dashboard'

const DEFAULT_RESOLUTION: ResolutionMetrics = { resolved: 0, pending: 0, escalated: 0 }
const DEFAULT_SATISFACTION: SatisfactionMetrics = {
  current_score: 0,
  target_score: 4.5,
  history: [],
}

export default function DashboardPage() {
  const [timePeriod, setTimePeriod] = useState<DashboardPeriod>('7d')
  const dashboard = useDashboardData(timePeriod)
  const { stats, metrics, isLoading } = dashboard
  const resolutionMetrics = dashboard.resolution ?? DEFAULT_RESOLUTION
  const satisfactionMetrics = dashboard.satisfaction ?? DEFAULT_SATISFACTION

  const formatNumber = (num: number): string => {
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`
    return num.toString()
  }

  const dashboardMetrics: Metric[] = [
    {
      label: 'Total de Conversas',
      value: formatNumber(stats?.total_conversations ?? 0),
      change: `+${metrics?.messages_today ?? 0} hoje`,
      trend: 'up' as const,
    },
    {
      label: 'Total de Mensagens',
      value: formatNumber(stats?.total_messages ?? 0),
      change: `${metrics?.messages_this_week ?? 0} esta semana`,
      trend: 'up' as const,
    },
    {
      label: 'Taxa de Sucesso',
      value: `${metrics?.response_rate ?? 0}%`,
      change: 'respostas enviadas',
      trend: 'up' as const,
    },
    {
      label: 'Satisfação dos Clientes',
      value: satisfactionMetrics.current_score > 0
        ? `${satisfactionMetrics.current_score}`
        : '--',
      change: satisfactionMetrics.current_score > 0
        ? `meta: ${satisfactionMetrics.target_score}`
        : 'sem avaliações ainda',
      trend: 'up' as const,
    },
  ]

  return (
    <div className="w-full bg-grid-pattern">
      <div className="max-w-[1400px] mx-auto p-4 sm:p-8 space-y-8 pb-12">

        {dashboard.error && (
          <div
            role="alert"
            className="flex items-center justify-between gap-4 rounded-2xl border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-status-error"
          >
            <span>{dashboard.error}</span>
            <button type="button" className="underline" onClick={() => void dashboard.refetch()}>
              Tentar de novo
            </button>
          </div>
        )}

        {/* TOP SECTION: Metrics Cards */}
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {isLoading ? (
            <div className="col-span-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-40 animate-pulse rounded-2xl bg-brand-card" />
              ))}
            </div>
          ) : (
            dashboardMetrics.map((metric, index) => (
              <MetricCard key={index} metric={metric} index={index} />
            ))
          )}
        </section>

        {/* SECTION DIVIDER */}
        <div className="flex items-center justify-between pt-4 animate-fade-in delay-300">
          <div>
            <h2 className="text-xl font-semibold text-content-light">Análise de Métricas</h2>
            <p className="text-sm text-content-muted mt-1">
              Visão detalhada do desempenho da automação e fluxo de dados.
            </p>
          </div>
        </div>

        {/* BOTTOM SECTION: Charts Grid */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-12">
          <LineChart
            data={dashboard.series}
            period={timePeriod}
            onPeriodChange={setTimePeriod}
            isLoading={dashboard.isSeriesFetching}
          />
          <BarChart
            channels={dashboard.channels}
            isLoading={isLoading}
          />
          <DonutChart
            data={resolutionMetrics}
            isLoading={isLoading}
          />
          <AreaChart
            metrics={satisfactionMetrics}
            isLoading={isLoading}
          />
        </section>
      </div>
    </div>
  )
}
