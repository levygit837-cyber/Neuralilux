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

/** Erro de uma chamada ao backend. `fieldErrors` traz os erros 422 do FastAPI por campo do corpo. */
export class GatewayApiError extends Error {
  readonly status: number
  readonly fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = 'GatewayApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

interface ValidationItem {
  loc?: unknown[]
  msg?: string
}

async function toApiError(response: Response): Promise<GatewayApiError> {
  let message = `Erro ${response.status}`
  const fieldErrors: Record<string, string> = {}
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') {
      message = body.detail
    } else if (Array.isArray(body.detail)) {
      const messages: string[] = []
      for (const item of body.detail as ValidationItem[]) {
        if (!item.msg) continue
        // O pydantic prefixa erros de validators próprios com "Value error, ".
        const text = item.msg.replace(/^Value error, /, '')
        messages.push(text)
        const field = item.loc?.[item.loc.length - 1]
        if (typeof field === 'string' && !(field in fieldErrors)) fieldErrors[field] = text
      }
      if (messages.length > 0) message = messages.join('; ')
    }
  } catch {
    /* corpo sem JSON */
  }
  return new GatewayApiError(response.status, message, fieldErrors)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token')
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!response.ok) throw await toApiError(response)
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
