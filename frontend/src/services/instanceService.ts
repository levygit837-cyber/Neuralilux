import axios from 'axios'

const EVOLUTION_API_URL =
  process.env.NEXT_PUBLIC_EVOLUTION_API_URL || 'http://localhost:8081'
const EVOLUTION_API_KEY =
  process.env.NEXT_PUBLIC_EVOLUTION_API_KEY || '3v0lut10n_4P1_K3y_S3cur3_2026!'

const BACKEND_API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type InstanceState = 'open' | 'close' | 'connecting'

const evolutionApi = axios.create({
  baseURL: EVOLUTION_API_URL,
  headers: {
    apikey: EVOLUTION_API_KEY,
    'Content-Type': 'application/json',
  },
})

export interface EvolutionInstance {
  instance: {
    instanceName: string
    instanceId: string
    status: InstanceState
    state: InstanceState
    qrcode?: {
      base64: string
      code: string
    }
  }
  socket?: {
    state: InstanceState
  }
}

interface RawEvolutionInstance {
  id?: string
  name?: string
  connectionStatus?: string
  status?: string
  instance?: Partial<EvolutionInstance['instance']>
  socket?: {
    state?: string
  }
}

export interface InstanceAgentStatusResponse {
  instance_id: string
  instance_name: string
  agent_enabled: boolean
  agent_id: string | null
  agent_name?: string | null
  message?: string
}

const getBackendHeaders = () => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null

  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

const rethrowApiError = (error: unknown, fallbackMessage: string): never => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    throw new Error(typeof detail === 'string' ? detail : fallbackMessage)
  }

  throw error instanceof Error ? error : new Error(fallbackMessage)
}

const normalizeState = (value?: string | null): InstanceState => {
  switch (value) {
    case 'open':
    case 'connected':
      return 'open'
    case 'connecting':
      return 'connecting'
    case 'close':
    case 'closed':
    case 'disconnected':
    default:
      return 'close'
  }
}

const normalizeInstance = (raw: RawEvolutionInstance): EvolutionInstance => {
  const rawInstance = raw.instance ?? {}
  const state = normalizeState(
    rawInstance.state ??
      rawInstance.status ??
      raw.socket?.state ??
      raw.connectionStatus ??
      raw.status
  )

  return {
    instance: {
      instanceName: rawInstance.instanceName ?? raw.name ?? '',
      instanceId: rawInstance.instanceId ?? raw.id ?? raw.name ?? '',
      status: normalizeState(rawInstance.status ?? state),
      state,
      qrcode: rawInstance.qrcode,
    },
    socket: {
      state: normalizeState(raw.socket?.state ?? state),
    },
  }
}

export const instanceService = {
  async fetchInstances(): Promise<EvolutionInstance[]> {
    const response = await evolutionApi.get<RawEvolutionInstance[]>('/instance/fetchInstances')

    if (!Array.isArray(response.data)) {
      return []
    }

    return response.data.map(normalizeInstance)
  },

  async fetchInstance(instanceId: string): Promise<EvolutionInstance> {
    const response = await evolutionApi.get<RawEvolutionInstance[] | RawEvolutionInstance>(
      `/instance/fetchInstances?instanceId=${instanceId}`
    )

    if (Array.isArray(response.data) && response.data.length > 0) {
      return normalizeInstance(response.data[0])
    }

    return normalizeInstance(response.data as RawEvolutionInstance)
  },

  async connectInstance(instanceName: string): Promise<{
    base64: string
    code: string
    count: number
  }> {
    const response = await evolutionApi.get(`/instance/connect/${instanceName}`)
    return response.data
  },

  async getConnectionState(instanceName: string): Promise<{
    instance: {
      instanceName: string
      state: InstanceState
    }
  }> {
    const response = await evolutionApi.get(`/instance/connectionState/${instanceName}`)
    return response.data
  },

  async logoutInstance(instanceName: string): Promise<void> {
    await evolutionApi.delete(`/instance/logout/${instanceName}`)
  },

  async deleteInstance(instanceName: string): Promise<void> {
    await evolutionApi.delete(`/instance/delete/${instanceName}`)
  },

  async updateAgentStatus(
    instanceName: string,
    agentEnabled: boolean
  ): Promise<InstanceAgentStatusResponse> {
    try {
      const response = await axios.patch<InstanceAgentStatusResponse>(
        `${BACKEND_API_URL}/api/v1/instances/${instanceName}/agent-status`,
        { agent_enabled: agentEnabled },
        {
          headers: getBackendHeaders(),
        }
      )
      return response.data
    } catch (error) {
      return rethrowApiError(error, 'Failed to update agent status')
    }
  },

  async getAgentStatus(instanceName: string): Promise<InstanceAgentStatusResponse> {
    try {
      const response = await axios.get<InstanceAgentStatusResponse>(
        `${BACKEND_API_URL}/api/v1/instances/${instanceName}/agent-status`,
        {
          headers: getBackendHeaders(),
        }
      )
      return response.data
    } catch (error) {
      return rethrowApiError(error, 'Failed to get agent status')
    }
  },

  async updateAgentBinding(
    instanceName: string,
    agentId: string | null
  ): Promise<InstanceAgentStatusResponse> {
    try {
      const response = await axios.patch<InstanceAgentStatusResponse>(
        `${BACKEND_API_URL}/api/v1/instances/${instanceName}/agent-binding`,
        { agent_id: agentId },
        {
          headers: getBackendHeaders(),
        }
      )
      return response.data
    } catch (error) {
      return rethrowApiError(error, 'Failed to update agent binding')
    }
  },
}
