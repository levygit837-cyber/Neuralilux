'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { SignOut } from '@phosphor-icons/react'
import { ROUTES } from '@/lib/constants'
import { authService } from '@/services/authService'
import { useAuthStore } from '@/stores/useAuthStore'

/** Encerra a sessão: o backend apaga o cookie `httpOnly` (só ele pode) e o store limpa o que é do usuário. */
export function LogoutButton() {
  const router = useRouter()
  const [isLeaving, setIsLeaving] = useState(false)

  const leave = async () => {
    setIsLeaving(true)
    try {
      await authService.logout()
    } finally {
      // Mesmo com o backend fora do ar o painel deve fechar; o cookie vence sozinho no prazo do JWT.
      useAuthStore.getState().logout()
      router.replace(ROUTES.LOGIN)
    }
  }

  return (
    <button
      type="button"
      onClick={() => void leave()}
      disabled={isLeaving}
      className="flex w-full items-center gap-4 rounded-xl px-4 py-3 text-sm font-medium text-content-muted hover:bg-brand-hover/50 hover:text-content-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary disabled:opacity-60"
    >
      <SignOut className="text-xl" aria-hidden="true" />
      Sair
    </button>
  )
}
