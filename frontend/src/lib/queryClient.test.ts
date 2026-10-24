// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearQueryCache, createQueryClient, getQueryClient } from '@/lib/queryClient'
import { queryKeys } from '@/lib/queryKeys'
import { apiRequest } from '@/services/http'
import { useAuthStore } from '@/stores/useAuthStore'

describe('createQueryClient', () => {
  it('não refaz tentativas: o erro do backend aparece na hora', () => {
    expect(createQueryClient().getDefaultOptions().queries?.retry).toBe(false)
  })
})

describe('cache na fronteira da sessão', () => {
  const seed = () => getQueryClient().setQueryData(queryKeys.menu, { categories: ['dados do usuário anterior'] })

  afterEach(() => {
    vi.unstubAllGlobals()
    clearQueryCache()
    useAuthStore.setState({ user: null, isAuthenticated: false })
  })

  it('o logout descarta os dados em cache', () => {
    seed()
    useAuthStore.getState().logout()
    expect(getQueryClient().getQueryData(queryKeys.menu)).toBeUndefined()
  })

  it('um novo login não herda o cache de quem estava antes', () => {
    seed()
    useAuthStore.getState().login({ id: 'u2', name: 'Outro', email: 'o@x.com' })
    expect(getQueryClient().getQueryData(queryKeys.menu)).toBeUndefined()
  })

  it('um 401 encerra a sessão e descarta o cache', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { pathname: '/dashboard', assign })
    const fetchMock = vi.fn().mockImplementation(async () => new Response('{"detail":"expirou"}', { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)
    useAuthStore.setState({ isAuthenticated: true })
    seed()

    await expect(apiRequest('/menu')).rejects.toMatchObject({ status: 401 })

    expect(getQueryClient().getQueryData(queryKeys.menu)).toBeUndefined()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
    expect(assign).toHaveBeenCalledWith('/login')
    // E o cookie httpOnly é apagado no backend, senão o proxy aceitaria a sessão de novo.
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/api/v1/auth/logout'))).toBe(true)
  })
})
