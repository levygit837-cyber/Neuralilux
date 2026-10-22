import { apiRequest, jsonBody } from '@/services/http'
import type { CompanyProfile, AIAgentConfig, WhatsAppConnection, ThemeConfig } from '@/types/settings'

export const settingsService = {
  getCompanyProfile: () =>
    apiRequest<CompanyProfile>('/settings/company', {}, 'Failed to fetch company profile'),

  updateCompanyProfile: (data: Partial<CompanyProfile>) =>
    apiRequest<CompanyProfile>('/settings/company', jsonBody('PATCH', data), 'Failed to update company profile'),

  getAIAgentConfig: () =>
    apiRequest<AIAgentConfig>('/settings/ai-agent', {}, 'Failed to fetch AI agent config'),

  updateAIAgentConfig: (data: Partial<AIAgentConfig>) =>
    apiRequest<AIAgentConfig>('/settings/ai-agent', jsonBody('PATCH', data), 'Failed to update AI agent config'),

  getWhatsAppConfig: () =>
    apiRequest<WhatsAppConnection>('/settings/whatsapp', {}, 'Failed to fetch WhatsApp config'),

  updateWhatsAppConfig: (data: Partial<WhatsAppConnection>) =>
    apiRequest<WhatsAppConnection>('/settings/whatsapp', jsonBody('PATCH', data), 'Failed to update WhatsApp config'),

  getThemeConfig: () => apiRequest<ThemeConfig>('/settings/theme', {}, 'Failed to fetch theme config'),

  updateThemeConfig: (data: Partial<ThemeConfig>) =>
    apiRequest<ThemeConfig>('/settings/theme', jsonBody('PATCH', data), 'Failed to update theme config'),

  testWhatsAppConnection: (apiUrl: string, apiKey: string) =>
    apiRequest<{ success: boolean; message: string }>(
      '/settings/whatsapp/test',
      jsonBody('POST', { apiUrl, apiKey }),
      'Failed to test WhatsApp connection'
    ),
}
