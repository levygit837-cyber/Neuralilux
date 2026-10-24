'use client'

import { useAuthStore } from '@/stores/useAuthStore'

/** Queries autenticadas só disparam com a sessão hidratada e o usuário logado (o cookie vai sozinho em cada chamada). */
export function useSessionReady(): boolean {
  return useAuthStore((state) => state.hasHydrated && state.isAuthenticated)
}
