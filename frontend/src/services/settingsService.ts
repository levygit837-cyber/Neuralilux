import { API_BASE_URL } from '@/lib/constants'
import type { CompanyProfile, AIAgentConfig, WhatsAppConnection, ThemeConfig } from '@/types/settings'

export const settingsService = {
  async getCompanyProfile(): Promise<CompanyProfile> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/company`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) {
      throw new Error('Failed to fetch company profile')
    }
    return response.json()
  },

  async updateCompanyProfile(data: Partial<CompanyProfile>): Promise<CompanyProfile> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/company`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error('Failed to update company profile')
    }
    return response.json()
  },

  async getAIAgentConfig(): Promise<AIAgentConfig> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/ai-agent`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) {
      throw new Error('Failed to fetch AI agent config')
    }
    return response.json()
  },

  async updateAIAgentConfig(data: Partial<AIAgentConfig>): Promise<AIAgentConfig> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/ai-agent`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error('Failed to update AI agent config')
    }
    return response.json()
  },

  async getWhatsAppConfig(): Promise<WhatsAppConnection> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/whatsapp`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) {
      throw new Error('Failed to fetch WhatsApp config')
    }
    return response.json()
  },

  async updateWhatsAppConfig(data: Partial<WhatsAppConnection>): Promise<WhatsAppConnection> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/whatsapp`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error('Failed to update WhatsApp config')
    }
    return response.json()
  },

  async getThemeConfig(): Promise<ThemeConfig> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/theme`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    if (!response.ok) {
      throw new Error('Failed to fetch theme config')
    }
    return response.json()
  },

  async updateThemeConfig(data: Partial<ThemeConfig>): Promise<ThemeConfig> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/theme`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    })
    if (!response.ok) {
      throw new Error('Failed to update theme config')
    }
    return response.json()
  },

  async testWhatsAppConnection(apiUrl: string, apiKey: string): Promise<{ success: boolean; message: string }> {
    const token = localStorage.getItem('token')
    const response = await fetch(`${API_BASE_URL}/api/v1/settings/whatsapp/test`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ apiUrl, apiKey }),
    })
    if (!response.ok) {
      throw new Error('Failed to test WhatsApp connection')
    }
    return response.json()
  },
}