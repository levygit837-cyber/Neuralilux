import { apiRequest, jsonBody } from '@/services/http'

export type InstanceStatus = 'connected' | 'disconnected' | 'connecting'

export interface Instance {
  /** UUID local; é o `instance_id` das Conversations. */
  id: string
  /** Nome na Evolution; é o que as rotas e o Socket.IO usam para endereçar a Instance. */
  name: string
  status: InstanceStatus
  agentEnabled: boolean
  profileName: string
  profilePicUrl: string
}

interface InstanceListItem {
  id: string
  name: string
  status: string
  agent_enabled: boolean
  profile_name?: string
  profile_pic_url?: string
}

export interface InstanceAgentStatusResponse {
  instance_id: string
  instance_name: string
  agent_enabled: boolean
  agent_id: string | null
  agent_name?: string | null
  message?: string
}

export interface ConnectResult {
  qrCode: string | null
  status: InstanceStatus
}

/** A Evolution fala `open`/`close`; o backend, `connected`/`disconnected`. A UI usa só o segundo vocabulário. */
export function normalizeInstanceStatus(value?: string | null): InstanceStatus {
  switch (value) {
    case 'open':
    case 'connected':
      return 'connected'
    case 'connecting':
      return 'connecting'
    default:
      return 'disconnected'
  }
}

const path = (name: string) => `/instances/${encodeURIComponent(name)}`

export const instanceService = {
  async list(): Promise<Instance[]> {
    const response = await apiRequest<{ instances: InstanceListItem[] }>('/instances/', {}, 'Falha ao listar as instâncias')
    return response.instances.map((item) => ({
      id: item.id,
      name: item.name,
      status: normalizeInstanceStatus(item.status),
      agentEnabled: item.agent_enabled,
      profileName: item.profile_name ?? '',
      profilePicUrl: item.profile_pic_url ?? '',
    }))
  },

  /** Cria a Instance na Evolution e a linha local; devolve o QR quando já disponível. */
  async create(name: string): Promise<{ qrCode: string | null }> {
    const response = await apiRequest<{ qr_code: string | null }>(
      path(name),
      { method: 'POST' },
      'Falha ao criar a instância'
    )
    return { qrCode: response.qr_code }
  },

  async getStatus(name: string): Promise<InstanceStatus> {
    const response = await apiRequest<{ status: string }>(`${path(name)}/status`, {}, 'Falha ao ler o status')
    return normalizeInstanceStatus(response.status)
  },

  async connect(name: string): Promise<ConnectResult> {
    const response = await apiRequest<{ qr_code: string | null; status: string }>(
      `${path(name)}/connect`,
      { method: 'POST' },
      'Falha ao gerar o QR code'
    )
    return { qrCode: response.qr_code, status: normalizeInstanceStatus(response.status) }
  },

  async logout(name: string): Promise<void> {
    await apiRequest(`${path(name)}/logout`, { method: 'DELETE' }, 'Falha ao desconectar')
  },

  async remove(name: string): Promise<void> {
    await apiRequest(path(name), { method: 'DELETE' }, 'Falha ao apagar a instância')
  },

  getAgentStatus: (name: string) =>
    apiRequest<InstanceAgentStatusResponse>(`${path(name)}/agent-status`, {}, 'Failed to get agent status'),

  updateAgentStatus: (name: string, agentEnabled: boolean) =>
    apiRequest<InstanceAgentStatusResponse>(
      `${path(name)}/agent-status`,
      jsonBody('PATCH', { agent_enabled: agentEnabled }),
      'Failed to update agent status'
    ),

  updateAgentBinding: (name: string, agentId: string | null) =>
    apiRequest<InstanceAgentStatusResponse>(
      `${path(name)}/agent-binding`,
      jsonBody('PATCH', { agent_id: agentId }),
      'Failed to update agent binding'
    ),
}
