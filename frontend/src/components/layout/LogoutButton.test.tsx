// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LogoutButton } from '@/components/layout/LogoutButton'
import { useAuthStore } from '@/stores/useAuthStore'

const replace = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace }) }))

const stubLogout = (response: Response) => {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('LogoutButton', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 'u1', name: 'Ana', email: 'ana@example.com' },
      isAuthenticated: true,
      hasHydrated: true,
    })
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
    vi.resetAllMocks()
    useAuthStore.setState({ user: null, isAuthenticated: false, hasHydrated: false })
  })

  it('backend apagou o cookie: limpa o store e vai para o login', async () => {
    stubLogout(new Response(null, { status: 204 }))
    render(<LogoutButton />)

    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'))
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })

  it('backend recusou (403 por CORS_ORIGINS): mostra o erro e não dá a sessão por encerrada', async () => {
    stubLogout(new Response('{"detail":"Origin not allowed"}', { status: 403 }))
    render(<LogoutButton />)

    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))

    expect((await screen.findByRole('alert')).textContent).toMatch(/não foi possível encerrar a sessão/i)
    expect(replace).not.toHaveBeenCalled()
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
    expect((screen.getByRole('button', { name: 'Sair' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('backend fora do ar também mantém a sessão e mostra o erro', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('fetch failed')))
    render(<LogoutButton />)

    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))

    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })
})
