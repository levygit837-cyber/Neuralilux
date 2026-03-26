export interface Metric {
  label: string
  value: string | number
  change: string
  trend: 'up' | 'down'
  icon?: string
}

export interface Activity {
  id: string
  title: string
  description: string
  timestamp: string
  icon?: string
  type?: 'message' | 'appointment' | 'sale'
}

export interface BusinessMetric {
  id: string
  name: string
  metrics: {
    label: string
    value: string | number
  }[]
}
