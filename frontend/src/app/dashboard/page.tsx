'use client'

import { useCallback, useEffect, useState } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { LineChart } from '@/components/dashboard/LineChart'
import { BarChart } from '@/components/dashboard/BarChart'
import { DonutChart } from '@/components/dashboard/DonutChart'
import { AreaChart } from '@/components/dashboard/AreaChart'
import {
  dashboardService,
  type DashboardStats,
  type DashboardMetrics,
} from '@/services/dashboardService'
import type {
  ChannelData,
  ConversationTimeSeriesPoint,
  Metric,
  ResolutionMetrics,
  SatisfactionMetrics,
} from '@/types/dashboard'
import { Export } from '@phosphor-icons/react'

const DEFAULT_RESOLUTION: ResolutionMetrics = { resolved: 0, pending: 0, escalated: 0 }
const DEFAULT_SATISFACTION: SatisfactionMetrics = {
  current_score: 0,
  target_score: 4.5,
  history: [],
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [timePeriod, setTimePeriod] = useState<'7d' | '30d' | '90d'>('7d')
  const [conversationsOverTime, setConversationsOverTime] = useState<ConversationTimeSeriesPoint[]>([])
  const [channelMetrics, setChannelMetrics] = useState<ChannelData[]>([])
  const [resolutionMetrics, setResolutionMetrics] = useState<ResolutionMetrics>(DEFAULT_RESOLUTION)
  const [satisfactionMetrics, setSatisfactionMetrics] = useState<SatisfactionMetrics>(DEFAULT_SATISFACTION)

  const [isLoading, setIsLoading] = useState(true)
  const [isTimeSeriesLoading, setIsTimeSeriesLoading] = useState(false)

  // Fetch all dashboard data on mount
  useEffect(() => {
    const loadAll = async () => {
      try {
        const [
          statsData,
          metricsData,
          timeSeriesData,
          channelData,
          resolutionData,
          satisfactionData,
        ] = await Promise.all([
          dashboardService.getStats(),
          dashboardService.getMetrics(),
          dashboardService.getConversationsOverTime(timePeriod),
          dashboardService.getChannelMetrics(),
          dashboardService.getResolutionMetrics(),
          dashboardService.getSatisfactionMetrics(),
        ])

        setStats(statsData)
        setMetrics(metricsData)
        setConversationsOverTime(timeSeriesData.data)
        setChannelMetrics(channelData.channels)
        setResolutionMetrics(resolutionData)
        setSatisfactionMetrics(satisfactionData)
      } catch (error) {
        console.error('Failed to load dashboard data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadAll()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Re-fetch time series when period changes (after first load)
  const handlePeriodChange = useCallback(async (period: '7d' | '30d' | '90d') => {
    setTimePeriod(period)
    setIsTimeSeriesLoading(true)
    try {
      const data = await dashboardService.getConversationsOverTime(period)
      setConversationsOverTime(data.data)
    } catch (error) {
      console.error('Failed to load conversations over time:', error)
    } finally {
      setIsTimeSeriesLoading(false)
    }
  }, [])

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
    <div className="flex min-h-screen bg-dark">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header title="Dashboard" showOnlineBadge={true} />
        <main className="flex-1 overflow-y-auto w-full bg-grid-pattern">
          <div className="max-w-[1400px] mx-auto p-8 space-y-8 pb-12">

            {/* TOP SECTION: Metrics Cards */}
            <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
              {isLoading ? (
                <div className="col-span-4 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-40 animate-pulse rounded-2xl bg-card" />
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
                <h2 className="text-xl font-semibold text-text-light">Análise de Métricas</h2>
                <p className="text-sm text-text-muted mt-1">
                  Visão detalhada do desempenho da automação e fluxo de dados.
                </p>
              </div>
              <button className="text-sm flex items-center gap-2 bg-card border border-border-color px-4 py-2 rounded-md hover:bg-hover hover:text-text-light transition">
                <Export weight="regular" /> Exportar Relatório
              </button>
            </div>

            {/* BOTTOM SECTION: Charts Grid */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-12">
              <LineChart
                data={conversationsOverTime}
                period={timePeriod}
                onPeriodChange={handlePeriodChange}
                isLoading={isTimeSeriesLoading}
              />
              <BarChart
                channels={channelMetrics}
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

            {/* Footer */}
            <div className="text-center text-xs text-text-muted/50 pb-4">
              Sistema NeuraliLux OS v2.4.1 © 2023. Todos os dados são processados em tempo real.
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
