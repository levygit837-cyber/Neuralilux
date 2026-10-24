// @vitest-environment jsdom
import { cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRestoreSession } from '@/hooks/useRestoreSession'
import { authService, type User } from '@/services/authService'
import type * as AuthServiceModule from '@/services/authService'
import { useAuthStore } from '@/stores/useAuthStore'

vi.mock('@/services/authService', async (importOriginal) => ({
  ...(await importOriginal<typeof AuthServiceModule>()),
  authService: { getCurrentUser: vi.fn() },
}))

const apiUser: User = {
  id: 'u1',
  email: 'ana@example.com',
  full_name: 'Ana Souza',
  company_id: null,
  is_active: true,
  is_superuser: false,
  created_at: '2026-01-01T00:00:00Z',
}

describe('useRestoreSession', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, isAuthenticated: false, hasHydrated: true })
  })

  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
    useAuthStore.setState({ user: null, isAuthenticated: false, hasHydrated: false })
  })

  it('cookie válido com store vazio: reidrata o usuário e libera as telas', async () => {
    vi.mocked(authService.getCurrentUser).mockResolvedValue(apiUser)
    renderHook(() => useRestoreSession())

    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(true))
    expect(useAuthStore.getState().user).toEqual({ id: 'u1', name: 'Ana Souza', email: 'ana@example.com' })
  })

  it('só consulta o backend depois de hidratar o store', () => {
    useAuthStore.setState({ hasHydrated: false })
    renderHook(() => useRestoreSession())

    expect(authService.getCurrentUser).not.toHaveBeenCalled()
  })

  it('store já preenchido não chama o backend', () => {
    useAuthStore.setState({ user: { id: 'u1', name: 'Ana', email: 'ana@example.com' }, isAuthenticated: true })
    renderHook(() => useRestoreSession())

    expect(authService.getCurrentUser).not.toHaveBeenCalled()
  })

  it('falha ao consultar deixa o store vazio, sem estourar', async () => {
    vi.mocked(authService.getCurrentUser).mockRejectedValue(new Error('rede'))
    renderHook(() => useRestoreSession())

    await waitFor(() => expect(authService.getCurrentUser).toHaveBeenCalledTimes(1))
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('depois de sair nesta tela não reidrata o usuário que acabou de sair', async () => {
    useAuthStore.setState({ user: { id: 'u1', name: 'Ana', email: 'ana@example.com' }, isAuthenticated: true })
    renderHook(() => useRestoreSession())

    useAuthStore.getState().logout()
    await Promise.resolve()

    expect(authService.getCurrentUser).not.toHaveBeenCalled()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })
})
