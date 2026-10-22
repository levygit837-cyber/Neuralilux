import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { InstanceStatus } from '@/services/instanceService'

export interface SelectedInstance {
  /** UUID local; filtra as Conversations. */
  id: string
  /** Nome na Evolution; endereça as rotas e o Socket.IO. */
  name: string
  status: InstanceStatus
}

interface InstanceStore {
  selectedInstance: SelectedInstance | null
  setSelectedInstance: (instance: SelectedInstance | null) => void
  clearInstance: () => void
}

export const useInstanceStore = create<InstanceStore>()(
  persist(
    (set) => ({
      selectedInstance: null,
      setSelectedInstance: (instance) => set({ selectedInstance: instance }),
      clearInstance: () => set({ selectedInstance: null }),
    }),
    {
      name: 'neuralilux-instance-storage',
      // v2: a seleção guardava o formato da Evolution (instanceName/instanceId/open|close).
      version: 2,
      migrate: () => ({ selectedInstance: null }),
      partialize: (state) => ({ selectedInstance: state.selectedInstance }),
    }
  )
)
