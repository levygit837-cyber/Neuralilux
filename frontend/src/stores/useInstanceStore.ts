import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface SelectedInstance {
  instanceName: string
  instanceId: string
  status: 'open' | 'close' | 'connecting'
}

interface InstanceStore {
  selectedInstance: SelectedInstance | null
  instances: SelectedInstance[]
  agentEnabled: boolean
  setSelectedInstance: (instance: SelectedInstance | null) => void
  setInstances: (instances: SelectedInstance[]) => void
  setAgentEnabled: (enabled: boolean) => void
  clearInstance: () => void
}

export const useInstanceStore = create<InstanceStore>()(
  persist(
    (set) => ({
      selectedInstance: null,
      instances: [],
      agentEnabled: true,
      setSelectedInstance: (instance) => set({ selectedInstance: instance }),
      setInstances: (instances) => set({ instances }),
      setAgentEnabled: (enabled) => set({ agentEnabled: enabled }),
      clearInstance: () => set({ selectedInstance: null, agentEnabled: true }),
    }),
    {
      name: 'neuralilux-instance-storage',
      partialize: (state) => ({ selectedInstance: state.selectedInstance, agentEnabled: state.agentEnabled }),
    }
  )
)
