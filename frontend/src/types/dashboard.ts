export type DashboardPeriod = '7d' | '30d' | '90d'

/** Número do período atual e o mesmo número no período anterior (de igual tamanho). */
export interface CountMetric {
  current: number
  previous: number
}

export interface ResponseRateMetric {
  current: number | null
  previous: number | null
  received: number
  answered: number
}

export interface DashboardOverview {
  conversations: CountMetric
  messages: CountMetric
  handoffs: CountMetric
  response_rate: ResponseRateMetric
}

export interface ConversationTimeSeriesPoint {
  date: string
  count: number
}

export interface ConversationTimeSeriesResponse {
  timezone: string
  data: ConversationTimeSeriesPoint[]
}

export interface InstanceMessages {
  instance_id: string
  name: string
  count: number
}

export interface MessagesByInstanceResponse {
  instances: InstanceMessages[]
}

export interface HandoffsByStatus {
  open: number
  in_progress: number
  closed: number
  expired: number
}
