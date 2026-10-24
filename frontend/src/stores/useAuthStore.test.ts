// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '@/stores/useAuthStore'

const user = { id: 'u1', name: 'Dono', email: 'dono@example.com' }
const TOKEN = 'eyJhbGciOiJIUzI1NiJ9.segredo.assinatura'

describe('useAuthStore: nenhuma credencial no JavaScript', () => {
  beforeEach(() => {
    localStorage.clear()
    useAuthStore.setState({ user: null, isAuthenticated: false, hasHydrated: false })
  })

  afterEach(() => useAuthStore.getState().logout())

  it('o estado não tem campo de token', () => {
    useAuthStore.getState().login(user)
    expect(Object.keys(useAuthStore.getState())).not.toContain('token')
  })

  it('login persiste só o usuário; document.cookie e localStorage não têm token', () => {
    useAuthStore.getState().login(user)

    const stored = JSON.parse(localStorage.getItem('auth-storage')!)
    expect(stored.state).toEqual({ user, isAuthenticated: true })
    expect(localStorage.getItem('token')).toBeNull()
    expect(document.cookie).toBe('')
  })

  it('logout limpa usuário e persistência', () => {
    useAuthStore.getState().login(user)
    useAuthStore.getState().logout()

    expect(useAuthStore.getState().user).toBeNull()
    expect(JSON.parse(localStorage.getItem('auth-storage')!).state).toEqual({ user: null, isAuthenticated: false })
  })

  it('ao hidratar, apaga o token que uma versão anterior deixou em cookie e em localStorage', async () => {
    document.cookie = `auth-storage=${encodeURIComponent(JSON.stringify({ state: { token: TOKEN } }))}; path=/`
    localStorage.setItem('token', TOKEN)

    await useAuthStore.persist.rehydrate()

    expect(localStorage.getItem('token')).toBeNull()
    expect(document.cookie).not.toContain('auth-storage')
    expect(useAuthStore.getState().hasHydrated).toBe(true)
  })
})
