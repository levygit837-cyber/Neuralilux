import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { User, AuthState } from '@/types/auth'
import { clearQueryCache } from '@/lib/queryClient'
import { useChatStore } from '@/stores/useChatStore'

interface AuthStore extends AuthState {
  hasHydrated: boolean
  login: (user: User) => void
  logout: () => void
  setUser: (user: User) => void
  setHasHydrated: (hasHydrated: boolean) => void
}

/**
 * Antes do ADR 0008 o JWT ficava num cookie legível por JavaScript (`auth-storage`) e em `localStorage['token']`.
 * Quem logou naquela época ainda os tem: apaga na hidratação, senão o token antigo segue exposto até vencer.
 */
function purgeLegacyCredentials(): void {
  document.cookie = 'auth-storage=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
  localStorage.removeItem('token')
}

/**
 * Quem está logado, para a interface. A credencial não passa por aqui: o JWT vive só no cookie `httpOnly`
 * que o backend grava (ADR 0008), fora do alcance de JavaScript. A fonte da verdade da sessão é esse cookie,
 * validado pelo `proxy.ts` e pelo backend; este store guarda apenas nome e e-mail, sem segredo.
 */
export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      hasHydrated: false,
      login: (user) => {
        clearQueryCache()
        set({ user, isAuthenticated: true })
      },
      logout: () => {
        // As Conversations e Messages em memória são do usuário que saiu.
        useChatStore.getState().reset()
        // E o cache de queries: o próximo login não pode ver dados do usuário que saiu.
        clearQueryCache()
        set({ user: null, isAuthenticated: false })
      },
      setUser: (user) => set({ user }),
      setHasHydrated: (hasHydrated) => set({ hasHydrated }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: ({ user, isAuthenticated }) => ({ user, isAuthenticated }),
      onRehydrateStorage: () => (state) => {
        purgeLegacyCredentials()
        state?.setHasHydrated(true)
      },
    }
  )
)
