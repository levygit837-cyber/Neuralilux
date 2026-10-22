import { apiRequest } from '@/services/http'
import type { AgentListItem } from '@/types/chat'

export const agentService = {
  getAgents: () => apiRequest<{ items: AgentListItem[]; total: number }>('/agents/', {}, 'Failed to get agents'),
}
