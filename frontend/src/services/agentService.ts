import { API_BASE_URL } from '@/lib/constants'
import type { AgentListItem } from '@/types/chat'

const getAuthHeaders = () => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null

  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export const agentService = {
  async getAgents(): Promise<{ items: AgentListItem[]; total: number }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/`, {
      headers: getAuthHeaders(),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || 'Failed to get agents')
    }

    return response.json()
  },
}
