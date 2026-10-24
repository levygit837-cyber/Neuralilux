'use client'

import { useRestoreSession } from '@/hooks/useRestoreSession'

/** Não desenha nada: reidrata o usuário do store a partir do cookie de sessão (ver `useRestoreSession`). */
export function SessionRestorer() {
  useRestoreSession()
  return null
}
