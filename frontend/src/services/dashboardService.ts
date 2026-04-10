import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'
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

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
})

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const dashboardService = {
  async getStats(): Promise<DashboardStats> {
    const response = await api.get('/dashboard/stats')
    return response.data
  },

  async getMetrics(): Promise<DashboardMetrics> {
    const response = await api.get('/dashboard/metrics')
    return response.data
  },

  async getConversationsOverTime(
    period: '7d' | '30d' | '90d' = '7d',
  ): Promise<ConversationTimeSeriesResponse> {
    const response = await api.get(`/dashboard/conversations-over-time?period=${period}`)
    return response.data
  },

  async getChannelMetrics(): Promise<ChannelMetricsResponse> {
    const response = await api.get('/dashboard/channel-metrics')
    return response.data
  },

  async getResolutionMetrics(): Promise<ResolutionMetrics> {
    const response = await api.get('/dashboard/resolution-metrics')
    return response.data
  },

  async getSatisfactionMetrics(): Promise<SatisfactionMetrics> {
    const response = await api.get('/dashboard/satisfaction-metrics')
    return response.data
  },
}
