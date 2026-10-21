import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Settings, SettingsTab, CompanyProfile, AIAgentConfig, WhatsAppConnection, ThemeConfig } from '@/types/settings'

interface SettingsStore {
  settings: Settings
  activeTab: SettingsTab
  setActiveTab: (tab: SettingsTab) => void
  updateCompany: (company: Partial<CompanyProfile>) => void
  updateAIAgent: (aiAgent: Partial<AIAgentConfig>) => void
  updateWhatsApp: (whatsapp: Partial<WhatsAppConnection>) => void
  updateTheme: (theme: Partial<ThemeConfig>) => void
  resetSettings: () => void
}

const defaultSettings: Settings = {
  company: {
    name: 'Neuralilux',
    businessType: 'Tecnologia',
    email: 'contato@neuralilux.com',
    phone: '+55 11 99999-0000',
  },
  aiAgent: {
    temperature: 0.7,
    maxTokens: 4096,
    timeout: 30,
    memoryEnabled: true,
    autoReplyEnabled: true,
    debugMode: false,
  },
  whatsapp: {
    apiUrl: 'https://api.evolution.com',
    apiKey: '',
    instanceName: 'neuralilux-prod',
    status: 'disconnected',
  },
  theme: {
    theme: 'dark',
    language: 'Português (BR)',
    timezone: 'America/Sao_Paulo (GMT-3)',
  },
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      settings: defaultSettings,
      activeTab: 'general',
      setActiveTab: (tab) => set({ activeTab: tab }),
      updateCompany: (company) =>
        set((state) => ({
          settings: {
            ...state.settings,
            company: { ...state.settings.company, ...company },
          },
        })),
      updateAIAgent: (aiAgent) =>
        set((state) => ({
          settings: {
            ...state.settings,
            aiAgent: { ...state.settings.aiAgent, ...aiAgent },
          },
        })),
      updateWhatsApp: (whatsapp) =>
        set((state) => ({
          settings: {
            ...state.settings,
            whatsapp: { ...state.settings.whatsapp, ...whatsapp },
          },
        })),
      updateTheme: (theme) =>
        set((state) => ({
          settings: {
            ...state.settings,
            theme: { ...state.settings.theme, ...theme },
          },
        })),
      resetSettings: () => set({ settings: defaultSettings }),
    }),
    {
      name: 'neuralilux-settings-storage',
      version: 1,
      // v0 guardava model e inference (provider legado); o provider agora é o gateway atribuído.
      migrate: (persisted) => {
        const state = persisted as { settings?: { aiAgent?: Record<string, unknown> } }
        if (state?.settings?.aiAgent) {
          delete state.settings.aiAgent.model
          delete state.settings.aiAgent.inference
        }
        return state as unknown as SettingsStore
      },
      partialize: (state) => ({ settings: state.settings, activeTab: state.activeTab }),
    }
  )
)