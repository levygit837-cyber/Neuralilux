'use client'

import { useQuery } from '@tanstack/react-query'
import { useSessionReady } from '@/hooks/useSessionReady'
import { queryKeys } from '@/lib/queryKeys'
import { dashboardService } from '@/services/dashboardService'
import type { DashboardPeriod } from '@/types/dashboard'

/**
 * Cada widget é uma query própria: um que falha mostra o erro sozinho e os outros seguem na tela.
 * O período entra na chave, então trocar de período refaz todos.
 */
export function useDashboardData(period: DashboardPeriod) {
  const enabled = useSessionReady()
  const overview = useQuery({
    queryKey: queryKeys.dashboardPart('overview', period),
    queryFn: () => dashboardService.getOverview(period),
    enabled,
  })
  const series = useQuery({
    queryKey: queryKeys.dashboardPart('conversations-over-time', period),
    queryFn: () => dashboardService.getConversationsOverTime(period),
    enabled,
  })
  const instances = useQuery({
    queryKey: queryKeys.dashboardPart('messages-by-instance', period),
    queryFn: () => dashboardService.getMessagesByInstance(period),
    enabled,
  })
  const handoffs = useQuery({
    queryKey: queryKeys.dashboardPart('handoffs', period),
    queryFn: () => dashboardService.getHandoffs(period),
    enabled,
  })
  return { overview, series, instances, handoffs }
}
