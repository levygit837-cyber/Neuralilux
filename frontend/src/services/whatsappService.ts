import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'

export interface ConnectionStatus {
  status: 'disconnected' | 'connecting' | 'connected'
  qrCode?: string
}

export const whatsappService = {
  async connect(): Promise<ConnectionStatus> {
    const response = await axios.post(`${API_BASE_URL}/api/whatsapp/connect`)
    return response.data
  },

  async disconnect(): Promise<ConnectionStatus> {
    const response = await axios.post(`${API_BASE_URL}/api/whatsapp/disconnect`)
    return response.data
  },

  async getStatus(): Promise<ConnectionStatus> {
    const response = await axios.get(`${API_BASE_URL}/api/whatsapp/status`)
    return response.data
  },

  async getQrCode(): Promise<{ qrCode: string }> {
    const response = await axios.get(`${API_BASE_URL}/api/whatsapp/qrcode`)
    return response.data
  },
}
