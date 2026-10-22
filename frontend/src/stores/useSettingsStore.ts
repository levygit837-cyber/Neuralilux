import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Settings, SettingsTab, ThemeConfig } from '@/types/settings'

interface SettingsStore {
  settings: Settings
  activeTab: SettingsTab
  setActiveTab: (tab: SettingsTab) => void
  updateTheme: (theme: Partial<ThemeConfig>) => void
  resetSettings: () => void
}

const defaultSettings: Settings = {
  theme: {
    theme: 'dark',
    language: 'Português (BR)',
  },
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      settings: defaultSettings,
      activeTab: 'general',
      setActiveTab: (tab) => set({ activeTab: tab }),
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
      version: 3,
      // Só preferências do painel ficam no navegador. Company e Agent moram no backend: as versões
      // anteriores guardavam `company` e `aiAgent` aqui (e `whatsapp` com a chave da Evolution), tudo descartado.
      migrate: (persisted) => {
        const state = persisted as { settings?: Record<string, unknown> }
        if (state?.settings) {
          delete state.settings.company
          delete state.settings.aiAgent
          delete state.settings.whatsapp
        }
        return state as unknown as SettingsStore
      },
      partialize: (state) => ({ settings: state.settings, activeTab: state.activeTab }),
    }
  )
)