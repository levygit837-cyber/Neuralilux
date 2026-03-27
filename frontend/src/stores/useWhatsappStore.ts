import { create } from 'zustand'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'open' | 'close'

interface WhatsappStore {
  instanceId: string | null
  status: ConnectionStatus
  qrCode: string | null
  isLoading: boolean
  error: string | null
  setInstanceId: (instanceId: string | null) => void
  setStatus: (status: ConnectionStatus) => void
  setQrCode: (qrCode: string | null) => void
  setLoading: (isLoading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export const useWhatsappStore = create<WhatsappStore>((set) => ({
  instanceId: null,
  status: 'disconnected',
  qrCode: null,
  isLoading: false,
  error: null,
  setInstanceId: (instanceId) => set({ instanceId }),
  setStatus: (status) => set({ status }),
  setQrCode: (qrCode) => set({ qrCode }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      instanceId: null,
      status: 'disconnected',
      qrCode: null,
      isLoading: false,
      error: null,
    }),
}))
