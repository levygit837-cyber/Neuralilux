export interface CompanyProfile {
  name: string
  businessType: string
  email: string
  phone: string
}

export interface AIAgentConfig {
  temperature: number
  maxTokens: number
  timeout: number
  memoryEnabled: boolean
  autoReplyEnabled: boolean
  debugMode: boolean
}

export interface WhatsAppConnection {
  apiUrl: string
  apiKey: string
  instanceName: string
  status: 'connected' | 'disconnected' | 'connecting'
}

export interface ThemeConfig {
  theme: 'dark' | 'light'
  language: string
  timezone: string
}

export interface Settings {
  company: CompanyProfile
  aiAgent: AIAgentConfig
  whatsapp: WhatsAppConnection
  theme: ThemeConfig
}

export type SettingsTab = 'general' | 'instance' | 'gateways'