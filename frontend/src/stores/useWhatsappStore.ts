import { create } from 'zustand'

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected'

interface WhatsappStore {
  status: ConnectionStatus
  qrCode: string | null
  isLoading: boolean
  error: string | null
  setStatus: (status: ConnectionStatus) => void
  setQrCode: (qrCode: string | null) => void
  setLoading: (isLoading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export const useWhatsappStore = create<WhatsappStore>((set) => ({
  status: 'disconnected',
  qrCode: null,
  isLoading: false,
  error: null,
  setStatus: (status) => set({ status }),
  setQrCode: (qrCode) => set({ qrCode }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      status: 'disconnected',
      qrCode: null,
      isLoading: false,
      error: null,
    }),
}))
