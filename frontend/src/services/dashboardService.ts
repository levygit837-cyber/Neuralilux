import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'

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
}
