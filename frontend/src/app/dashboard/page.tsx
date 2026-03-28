'use client'

import { useEffect, useState } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { dashboardService, DashboardStats, DashboardMetrics } from '@/services/dashboardService'
import type { Metric } from '@/types/dashboard'

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        const [statsData, metricsData] = await Promise.all([
          dashboardService.getStats(),
          dashboardService.getMetrics(),
        ])
        setStats(statsData)
        setMetrics(metricsData)
      } catch (error) {
        console.error('Failed to load dashboard data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboardData()
  }, [])

  const formatNumber = (num: number): string => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`
    }
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
      value: formatNumber(stats?.total_contacts ?? 0),
      change: 'contatos ativos',
      trend: 'up' as const,
    },
  ]

  return (
    <div className="flex min-h-screen bg-dark">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header title="Dashboard" />
        <main className="flex-1 overflow-auto p-8">
          <div className="mx-auto max-w-7xl space-y-8">
            {/* Metrics Section */}
            <section>
              <h2 className="mb-4 text-xl font-bold text-text-light">Visão Geral</h2>
              {isLoading ? (
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="h-32 animate-pulse rounded-lg bg-card"
                    />
                  ))}
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
                  {dashboardMetrics.map((metric, index) => (
                    <MetricCard key={index} metric={metric} />
                  ))}
                </div>
              )}
            </section>

            {/* Info Section */}
            <section>
              <h2 className="mb-4 text-xl font-bold text-text-light">
                Informações
              </h2>
              <div className="rounded-lg border border-border-color bg-card p-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between border-b border-border-color pb-4">
                    <span className="text-text-gray">Mensagens Hoje</span>
                    <span className="font-semibold text-text-light">
                      {isLoading ? '...' : metrics?.messages_today ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between border-b border-border-color pb-4">
                    <span className="text-text-gray">Mensagens Esta Semana</span>
                    <span className="font-semibold text-text-light">
                      {isLoading ? '...' : metrics?.messages_this_week ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between border-b border-border-color pb-4">
                    <span className="text-text-gray">Taxa de Sucesso</span>
                    <span className="font-semibold text-text-light">
                      {isLoading ? '...' : `${metrics?.response_rate ?? 0}%`}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-text-gray">Satisfação dos Clientes</span>
                    <span className="font-semibold text-text-light">
                      {isLoading ? '...' : stats?.total_contacts ?? 0}
                    </span>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  )
}
