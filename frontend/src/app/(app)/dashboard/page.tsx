'use client'

import { useState } from 'react'
import { Chats, Headset, PaperPlaneRight, CheckCircle } from '@phosphor-icons/react'
import { HandoffsChart } from '@/components/dashboard/HandoffsChart'
import { InstanceMessagesChart } from '@/components/dashboard/InstanceMessagesChart'
import { LineChart } from '@/components/dashboard/LineChart'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { PeriodSelector } from '@/components/dashboard/PeriodSelector'
import { errorMessage } from '@/components/dashboard/WidgetError'
import { useDashboardData } from '@/hooks/useDashboardData'
import { countTrend, rateTrend } from '@/lib/dashboardTrend'
import type { DashboardPeriod } from '@/types/dashboard'

const PERIOD_DAYS: Record<DashboardPeriod, number> = { '7d': 7, '30d': 30, '90d': 90 }

const formatNumber = (value: number): string => (value >= 1000 ? `${(value / 1000).toFixed(1)}k` : value.toString())

export default function DashboardPage() {
  const [period, setPeriod] = useState<DashboardPeriod>('7d')
  const { overview, series, instances, handoffs } = useDashboardData(period)
  const data = overview.data
  const overviewError = overview.isError ? errorMessage(overview.error) : null
  const retryOverview = () => void overview.refetch()
  const rate = data?.response_rate

  return (
    <div className="w-full bg-grid-pattern">
      <div className="mx-auto max-w-[1400px] space-y-8 p-4 pb-12 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-content-light">Visão geral</h2>
            <p className="mt-1 text-sm text-content-muted">
              Últimos {PERIOD_DAYS[period]} dias, comparados com os {PERIOD_DAYS[period]} dias anteriores.
            </p>
          </div>
          <PeriodSelector period={period} onChange={setPeriod} />
        </div>

        <section aria-label="Resumo" className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            index={0}
            label="Conversas novas"
            icon={Chats}
            value={data && formatNumber(data.conversations.current)}
            trend={data && countTrend(data.conversations.current, data.conversations.previous)}
            error={overviewError}
            onRetry={retryOverview}
          />
          <MetricCard
            index={1}
            label="Mensagens"
            icon={PaperPlaneRight}
            value={data && formatNumber(data.messages.current)}
            trend={data && countTrend(data.messages.current, data.messages.previous)}
            error={overviewError}
            onRetry={retryOverview}
          />
          <MetricCard
            index={2}
            label="Handoffs"
            icon={Headset}
            value={data && formatNumber(data.handoffs.current)}
            caption="Tickets abertos no período"
            trend={data && countTrend(data.handoffs.current, data.handoffs.previous)}
            error={overviewError}
            onRetry={retryOverview}
          />
          <MetricCard
            index={3}
            label="Taxa de resposta"
            icon={CheckCircle}
            value={rate && (rate.current === null ? '--' : `${rate.current}%`)}
            caption={
              rate &&
              (rate.received === 0
                ? 'nenhuma mensagem de cliente no período'
                : `${rate.answered} de ${rate.received} mensagens de clientes respondidas`)
            }
            trend={rate && rateTrend(rate.current, rate.previous)}
            progress={rate?.current}
            error={overviewError}
            onRetry={retryOverview}
          />
        </section>

        <section aria-label="Gráficos" className="grid grid-cols-1 gap-6 pb-12 lg:grid-cols-2">
          <LineChart
            data={series.data?.data}
            period={period}
            error={series.isError ? errorMessage(series.error) : null}
            onRetry={() => void series.refetch()}
          />
          <InstanceMessagesChart
            instances={instances.data?.instances}
            error={instances.isError ? errorMessage(instances.error) : null}
            onRetry={() => void instances.refetch()}
          />
          <HandoffsChart
            data={handoffs.data}
            error={handoffs.isError ? errorMessage(handoffs.error) : null}
            onRetry={() => void handoffs.refetch()}
          />
        </section>
      </div>
    </div>
  )
}
