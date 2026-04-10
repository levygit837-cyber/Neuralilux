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

// --- Chart data types ---

export interface ConversationTimeSeriesPoint {
  date: string
  count: number
}

export interface ConversationTimeSeriesResponse {
  data: ConversationTimeSeriesPoint[]
  period: '7d' | '30d' | '90d'
}

export interface ChannelData {
  name: string
  count: number
}

export interface ChannelMetricsResponse {
  channels: ChannelData[]
}

export interface ResolutionMetrics {
  resolved: number
  pending: number
  escalated: number
}

export interface SatisfactionMetrics {
  current_score: number
  target_score: number
  history: Array<{
    month: string
    score: number
  }>
}
