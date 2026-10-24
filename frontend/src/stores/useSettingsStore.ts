import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { SettingsTab } from '@/types/settings'

interface SettingsStore {
  activeTab: SettingsTab
  setActiveTab: (tab: SettingsTab) => void
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      activeTab: 'general',
      setActiveTab: (tab) => set({ activeTab: tab }),
    }),
    {
      name: 'neuralilux-settings-storage',
      version: 4,
      // Só a aba ativa fica no navegador. Company e Agent moram no backend; tema e idioma foram
      // removidos (o produto é só dark) e as versões anteriores guardavam `settings` aqui.
      migrate: (persisted) => {
        const tab = (persisted as { activeTab?: SettingsTab } | null)?.activeTab
        return { activeTab: tab ?? 'general' } as SettingsStore
      },
      partialize: (state) => ({ activeTab: state.activeTab }),
    }
  )
)
