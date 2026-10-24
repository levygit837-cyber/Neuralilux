'use client'

import { useEffect, useRef } from 'react'
import { authService, toSessionUser } from '@/services/authService'
import { useAuthStore } from '@/stores/useAuthStore'

/**
 * O cookie `httpOnly` é a sessão; o store só guarda nome e e-mail para a interface. Se o proxy deixou a pessoa entrar
 * (cookie válido) mas o store veio vazio (outra porta, `localStorage` limpo), `useSessionReady` ficaria `false` para
 * sempre e nenhuma tela buscaria dados. Aqui o usuário é reidratado de `/auth/me`. Quem já estava logado e saiu
 * nesta montagem não reidrata: o logout limpa o store de propósito.
 */
export function useRestoreSession(): void {
  const hasHydrated = useAuthStore((state) => state.hasHydrated)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const wasAuthenticated = useRef(false)

  useEffect(() => {
    if (!hasHydrated) return
    if (isAuthenticated) {
      wasAuthenticated.current = true
      return
    }
    if (wasAuthenticated.current) return

    let cancelled = false
    authService
      .getCurrentUser()
      .then((user) => {
        if (!cancelled) useAuthStore.getState().login(toSessionUser(user))
      })
      .catch(() => {
        // 401 já encerrou a sessão na camada HTTP; qualquer outra falha deixa o store vazio e as telas em espera.
      })
    return () => {
      cancelled = true
    }
  }, [hasHydrated, isAuthenticated])
}
