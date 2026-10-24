'use client'

import { useQuery } from '@tanstack/react-query'
import { useSessionReady } from '@/hooks/useSessionReady'
import { queryKeys } from '@/lib/queryKeys'
import { dashboardService } from '@/services/dashboardService'

export type DashboardPeriod = '7d' | '30d' | '90d'

/** Cada bloco do dashboard é uma query própria: o período só refaz a série temporal. */
export function useDashboardData(period: DashboardPeriod) {
  const enabled = useSessionReady()
  const stats = useQuery({ queryKey: queryKeys.dashboardPart('stats'), queryFn: dashboardService.getStats, enabled })
  const metrics = useQuery({ queryKey: queryKeys.dashboardPart('metrics'), queryFn: dashboardService.getMetrics, enabled })
  const series = useQuery({
    queryKey: queryKeys.dashboardPart('conversations-over-time', period),
    queryFn: () => dashboardService.getConversationsOverTime(period),
    enabled,
    placeholderData: (previous) => previous,
  })
  const channels = useQuery({
    queryKey: queryKeys.dashboardPart('channels'),
    queryFn: dashboardService.getChannelMetrics,
    enabled,
  })
  const resolution = useQuery({
    queryKey: queryKeys.dashboardPart('resolution'),
    queryFn: dashboardService.getResolutionMetrics,
    enabled,
  })
  const satisfaction = useQuery({
    queryKey: queryKeys.dashboardPart('satisfaction'),
    queryFn: dashboardService.getSatisfactionMetrics,
    enabled,
  })

  const all = [stats, metrics, series, channels, resolution, satisfaction]
  const failed = all.find((query) => query.isError)
  return {
    stats: stats.data,
    metrics: metrics.data,
    series: series.data?.data ?? [],
    channels: channels.data?.channels ?? [],
    resolution: resolution.data,
    satisfaction: satisfaction.data,
    isLoading: all.some((query) => query.isPending),
    isSeriesFetching: series.isFetching,
    error: failed?.error instanceof Error ? failed.error.message : failed ? 'Falha ao carregar o dashboard' : null,
    refetch: () => Promise.all(all.map((query) => query.refetch())),
  }
}
