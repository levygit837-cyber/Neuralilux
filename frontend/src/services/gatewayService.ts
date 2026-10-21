import { API_BASE_URL } from '@/lib/constants'
import type {
  AgentType,
  Gateway,
  GatewayAssignment,
  GatewayInput,
  GatewayModel,
  GatewayModelInput,
  ProbeResult,
} from '@/types/gateway'

const BASE = `${API_BASE_URL}/api/v1/gateways`

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token')
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!response.ok) {
    let detail = `Erro ${response.status}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* corpo sem JSON */
    }
    throw new Error(detail)
  }
  return response.status === 204 ? (undefined as T) : response.json()
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) })

export const gatewayService = {
  list: () => request<Gateway[]>('/'),
  create: (data: GatewayInput) => request<Gateway>('/', json('POST', data)),
  update: (id: string, data: Partial<GatewayInput>) => request<Gateway>(`/${id}`, json('PATCH', data)),
  remove: (id: string) => request<void>(`/${id}`, { method: 'DELETE' }),
  remoteModels: (id: string) => request<{ models: string[] }>(`/${id}/remote-models`),

  createModel: (gatewayId: string, data: GatewayModelInput) =>
    request<GatewayModel>(`/${gatewayId}/models`, json('POST', data)),
  updateModel: (id: string, data: Partial<GatewayModelInput>) =>
    request<GatewayModel>(`/models/${id}`, json('PATCH', data)),
  removeModel: (id: string) => request<void>(`/models/${id}`, { method: 'DELETE' }),
  testModel: (id: string) => request<ProbeResult>(`/models/${id}/test`, { method: 'POST' }),

  assignments: () => request<GatewayAssignment[]>('/assignments'),
  assign: (agentType: AgentType, gatewayModelId: string) =>
    request<GatewayAssignment>(`/assignments/${agentType}`, json('PUT', { gateway_model_id: gatewayModelId })),
  unassign: (agentType: AgentType) => request<void>(`/assignments/${agentType}`, { method: 'DELETE' }),
}
