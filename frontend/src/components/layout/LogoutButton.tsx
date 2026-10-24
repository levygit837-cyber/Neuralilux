'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { SignOut } from '@phosphor-icons/react'
import { ROUTES } from '@/lib/constants'
import { authService } from '@/services/authService'
import { useAuthStore } from '@/stores/useAuthStore'

/**
 * Encerra a sessão: o backend apaga o cookie `httpOnly` (só ele pode) e o store limpa o que é do usuário.
 * Se o backend recusar, o cookie segue valendo: o painel fica aberto e mostra o erro em vez de fingir que saiu.
 */
export function LogoutButton() {
  const router = useRouter()
  const [isLeaving, setIsLeaving] = useState(false)
  const [failed, setFailed] = useState(false)

  const leave = async () => {
    setIsLeaving(true)
    setFailed(false)
    try {
      await authService.logout()
    } catch {
      setFailed(true)
      setIsLeaving(false)
      return
    }
    useAuthStore.getState().logout()
    router.replace(ROUTES.LOGIN)
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => void leave()}
        disabled={isLeaving}
        className="flex w-full items-center gap-4 rounded-xl px-4 py-3 text-sm font-medium text-content-muted hover:bg-brand-hover/50 hover:text-content-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-60"
      >
        <SignOut className="text-xl" aria-hidden="true" />
        Sair
      </button>
      {failed && (
        <p role="alert" className="px-4 pt-2 text-xs text-status-error">
          Não foi possível encerrar a sessão. Tente de novo.
        </p>
      )}
    </div>
  )
}
