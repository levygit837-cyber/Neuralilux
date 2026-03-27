import axios from 'axios'
import { API_BASE_URL } from '@/lib/constants'

export interface ConnectionStatus {
  instance_id: string
  status: 'disconnected' | 'connecting' | 'connected' | 'open' | 'close'
  qr_code?: string
  qrCode?: string
  message?: string
}

export interface QrCodeResponse {
  instance_id: string
  qr_code: string
  status: string
  message?: string
}

export const whatsappService = {
  /**
   * Initiate connection by getting QR code.
   * The QR code must be scanned with WhatsApp mobile app to complete connection.
   */
  async connect(instanceId: string): Promise<QrCodeResponse> {
    const response = await axios.get(`${API_BASE_URL}/api/v1/whatsapp/qr`, {
      params: { instance_id: instanceId },
    })
    return response.data
  },

  async disconnect(instanceId: string): Promise<ConnectionStatus> {
    const response = await axios.post(`${API_BASE_URL}/api/v1/whatsapp/disconnect`, null, {
      params: { instance_id: instanceId },
    })
    return response.data
  },

  async getStatus(instanceId: string): Promise<ConnectionStatus> {
    const response = await axios.get(`${API_BASE_URL}/api/v1/whatsapp/status`, {
      params: { instance_id: instanceId },
    })
    return response.data
  },

  async getQrCode(instanceId: string): Promise<QrCodeResponse> {
    const response = await axios.get(`${API_BASE_URL}/api/v1/whatsapp/qr`, {
      params: { instance_id: instanceId },
    })
    return response.data
  },
}
