import { apiRequest } from '@/services/http'
import type {
  ChannelMetricsResponse,
  ConversationTimeSeriesResponse,
  ResolutionMetrics,
  SatisfactionMetrics,
} from '@/types/dashboard'

export interface DashboardStats {
  total_conversations: number
  total_messages: number
  active_instances: number
  total_contacts: number
}

export interface DashboardMetrics {
  messages_today: number
  messages_this_week: number
  response_rate: number
  avg_response_time: number | null
}

export const dashboardService = {
  getStats: () => apiRequest<DashboardStats>('/dashboard/stats'),

  getMetrics: () => apiRequest<DashboardMetrics>('/dashboard/metrics'),

  getConversationsOverTime: (period: '7d' | '30d' | '90d' = '7d') =>
    apiRequest<ConversationTimeSeriesResponse>(`/dashboard/conversations-over-time?period=${period}`),

  getChannelMetrics: () => apiRequest<ChannelMetricsResponse>('/dashboard/channel-metrics'),

  getResolutionMetrics: () => apiRequest<ResolutionMetrics>('/dashboard/resolution-metrics'),

  getSatisfactionMetrics: () => apiRequest<SatisfactionMetrics>('/dashboard/satisfaction-metrics'),
}
