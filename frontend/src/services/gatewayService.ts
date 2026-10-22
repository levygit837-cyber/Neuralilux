import { apiRequest, jsonBody as json } from '@/services/http'
import type {
  AgentType,
  Gateway,
  GatewayAssignment,
  GatewayInput,
  GatewayModel,
  GatewayModelInput,
  ProbeResult,
} from '@/types/gateway'

const request = <T>(path: string, init: RequestInit = {}) => apiRequest<T>(`/gateways${path}`, init)

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
