import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'
import { getCookie } from '@/lib/cookieStorage'

// Instance interface matching backend response format
export interface Instance {
  instance_id: string
  name: string
  status: string
  owner: string
  profile_name: string
  profile_pic_url: string
  token: string
  server_url: string
}

export interface InstanceListResponse {
  instances: Instance[]
  total: number
}

export interface InstanceStatusResponse {
  instance_id: string
  status: string
  evolution_state: string
  raw: Record<string, unknown>
}

export interface InstanceConnectResponse {
  instance_id: string
  qr_code: string | null
  status: string
  message: string
}

export interface InstanceActionResponse {
  instance_id: string
  status: string
  message: string
  raw?: Record<string, unknown>
}

// Create axios instance with auth interceptor
const api = axios.create({
  baseURL: API_BASE_URL,
})

api.interceptors.request.use((config) => {
  const token = getCookie('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

const INSTANCES_BASE = '/api/v1/instances'

export const instanceService = {
  /**
   * List all WhatsApp instances from the backend.
   * Backend fetches from Evolution API and normalizes the response.
   * NO AUTH REQUIRED per backend endpoint definition.
   */
  async fetchInstances(): Promise<InstanceListResponse> {
    const response = await api.get<InstanceListResponse>(`${INSTANCES_BASE}/`)
    return response.data
  },

  /**
   * Get the connection status of a specific instance.
   * NO AUTH REQUIRED per backend endpoint definition.
   */
  async getInstanceStatus(instanceId: string): Promise<InstanceStatusResponse> {
    const response = await api.get<InstanceStatusResponse>(
      `${INSTANCES_BASE}/${instanceId}/status`
    )
    return response.data
  },

  /**
   * Connect a WhatsApp instance (fetches QR code for scanning).
   * Requires authentication.
   */
  async connectInstance(instanceId: string): Promise<InstanceConnectResponse> {
    const response = await api.post<InstanceConnectResponse>(
      `${INSTANCES_BASE}/${instanceId}/connect`
    )
    return response.data
  },

  /**
   * Logout/disconnect a WhatsApp instance.
   * Requires authentication.
   */
  async logoutInstance(instanceId: string): Promise<InstanceActionResponse> {
    const response = await api.delete<InstanceActionResponse>(
      `${INSTANCES_BASE}/${instanceId}/logout`
    )
    return response.data
  },

  /**
   * Delete a WhatsApp instance permanently.
   * Requires authentication.
   */
  async deleteInstance(instanceId: string): Promise<InstanceActionResponse> {
    const response = await api.delete<InstanceActionResponse>(
      `${INSTANCES_BASE}/${instanceId}`
    )
    return response.data
  },

  /**
   * Create a new WhatsApp instance and connect it.
   * Requires authentication.
   */
  async createInstance(instanceId: string): Promise<InstanceConnectResponse> {
    const response = await api.post<InstanceConnectResponse>(
      `${INSTANCES_BASE}/${instanceId}`
    )
    return response.data
  },
}
