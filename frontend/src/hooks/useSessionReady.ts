'use client'

import { useAuthStore } from '@/stores/useAuthStore'

/** Queries autenticadas só disparam com a sessão hidratada e um token. */
export function useSessionReady(): boolean {
  return useAuthStore((state) => state.hasHydrated && Boolean(state.token))
}
