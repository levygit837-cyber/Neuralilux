import { create } from 'zustand'
import type { Metric, Activity, BusinessMetric } from '@/types/dashboard'

interface DashboardStore {
  metrics: Metric[]
  activities: Activity[]
  businessMetrics: BusinessMetric[]
  setMetrics: (metrics: Metric[]) => void
  setActivities: (activities: Activity[]) => void
  setBusinessMetrics: (businessMetrics: BusinessMetric[]) => void
}

export const useDashboardStore = create<DashboardStore>((set) => ({
  metrics: [],
  activities: [],
  businessMetrics: [],
  setMetrics: (metrics) => set({ metrics }),
  setActivities: (activities) => set({ activities }),
  setBusinessMetrics: (businessMetrics) => set({ businessMetrics }),
}))
