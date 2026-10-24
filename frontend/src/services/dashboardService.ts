import { apiRequest } from '@/services/http'
import type {
  ConversationTimeSeriesResponse,
  DashboardOverview,
  DashboardPeriod,
  HandoffsByStatus,
  MessagesByInstanceResponse,
} from '@/types/dashboard'

/** Cada rota é um widget do dashboard; as definições dos números estão em `docs/dashboard.md`. */
export const dashboardService = {
  getOverview: (period: DashboardPeriod) => apiRequest<DashboardOverview>(`/dashboard/overview?period=${period}`),

  getConversationsOverTime: (period: DashboardPeriod) =>
    apiRequest<ConversationTimeSeriesResponse>(`/dashboard/conversations-over-time?period=${period}`),

  getMessagesByInstance: (period: DashboardPeriod) =>
    apiRequest<MessagesByInstanceResponse>(`/dashboard/messages-by-instance?period=${period}`),

  getHandoffs: (period: DashboardPeriod) => apiRequest<HandoffsByStatus>(`/dashboard/handoffs?period=${period}`),
}
