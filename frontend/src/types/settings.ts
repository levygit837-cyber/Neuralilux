export interface CompanyProfile {
  name: string
  businessType: string
  email: string
  phone: string
}

export type InferenceProvider = 'gemini' | 'lm_studio'
export type LocalModel = 'nemotron' | 'qwen'

export interface InferenceConfig {
  provider: InferenceProvider
  localModel: LocalModel
  geminiApiKey: string
  geminiModel: string
  lmStudioUrl: string
}

export interface AIAgentConfig {
  model: string
  temperature: number
  maxTokens: number
  timeout: number
  memoryEnabled: boolean
  autoReplyEnabled: boolean
  debugMode: boolean
  inference: InferenceConfig
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

export type SettingsTab = 'general' | 'instance'