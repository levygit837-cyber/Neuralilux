import { API_BASE_URL } from '@/lib/constants'
import type { AgentListItem, AgentMessage, AgentSessionMessage, AgentSessionSummary } from '@/types/agent'

interface SendMessageResponse {
  message_id: string
  response: string
  thinking?: string
  intent?: string
  session_id: string
}

interface CreateSessionResponse {
  session_id: string
}

const getAuthHeaders = () => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null

  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export const agentService = {
  async sendMessage(
    content: string,
    sessionId?: string,
    companyId?: string,
    userId?: string
  ): Promise<SendMessageResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/chat`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        message: content,
        session_id: sessionId,
        company_id: companyId,
        user_id: userId,
      }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || 'Failed to send message to agent')
    }

    return response.json()
  },

  async getMessages(): Promise<{ items: AgentMessage[] }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/messages`, {
      headers: getAuthHeaders(),
    })

    if (!response.ok) {
      throw new Error('Failed to get agent messages')
    }

    return response.json()
  },

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

  async createSession(companyId?: string, userId?: string): Promise<CreateSessionResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/chat/session`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        company_id: companyId,
        user_id: userId,
      }),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || 'Failed to create chat session')
    }

    return response.json()
  },

  async getSessionMessages(
    sessionId: string
  ): Promise<{ items: AgentSessionMessage[]; total: number }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/chat/session/${sessionId}/messages`, {
      headers: getAuthHeaders(),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || 'Failed to load agent session messages')
    }

    return response.json()
  },

  async getSessions(limit = 20): Promise<{ items: AgentSessionSummary[]; total: number }> {
    const response = await fetch(`${API_BASE_URL}/api/v1/agents/chat/sessions?limit=${limit}`, {
      headers: getAuthHeaders(),
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || 'Failed to load agent sessions')
    }

    return response.json()
  },
}
