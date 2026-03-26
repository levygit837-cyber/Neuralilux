import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'
import type { Metric, Activity, BusinessMetric } from '@/types/dashboard'

export const dashboardService = {
  async getMetrics(): Promise<Metric[]> {
    const response = await axios.get(`${API_BASE_URL}/api/dashboard/metrics`)
    return response.data
  },

  async getActivities(): Promise<Activity[]> {
    const response = await axios.get(`${API_BASE_URL}/api/dashboard/activities`)
    return response.data
  },

  async getBusinessMetrics(): Promise<BusinessMetric[]> {
    const response = await axios.get(`${API_BASE_URL}/api/dashboard/business-metrics`)
    return response.data
  },
}
