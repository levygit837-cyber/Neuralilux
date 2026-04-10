import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { User, AuthState } from '@/types/auth'
import { cookieStorage } from '@/lib/cookieStorage'
import { isTokenExpired, syncTokenToLocalStorage } from '@/lib/authToken'

interface AuthStore extends AuthState {
  hasHydrated: boolean
  login: (user: User, token: string) => void
  logout: () => void
  setUser: (user: User) => void
  setHasHydrated: (hasHydrated: boolean) => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      hasHydrated: false,
      login: (user, token) => {
        syncTokenToLocalStorage(token)
        set({ user, token, isAuthenticated: true })
      },
      logout: () => {
        syncTokenToLocalStorage(null)
        set({ user: null, token: null, isAuthenticated: false })
      },
      setUser: (user) => set({ user }),
      setHasHydrated: (hasHydrated) => set({ hasHydrated }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => cookieStorage),
      onRehydrateStorage: () => (state) => {
        if (state?.token && isTokenExpired(state.token)) {
          state.logout()
        } else {
          syncTokenToLocalStorage(state?.token ?? null)
        }
        state?.setHasHydrated(true)
      },
    }
  )
)
