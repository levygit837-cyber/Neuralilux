// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCompanySettings } from '@/hooks/useCompanySettings'
import { authService, type User } from '@/services/authService'
import { companyService } from '@/services/companyService'
import { HttpError } from '@/services/http'
import { useAuthStore } from '@/stores/useAuthStore'
import { queryWrapper } from '@/test/queryWrapper'
import type { AgentSettings, Company } from '@/types/company'

vi.mock('@/services/authService', () => ({ authService: { getCurrentUser: vi.fn() } }))
vi.mock('@/services/companyService', () => ({
  companyService: { get: vi.fn(), update: vi.fn(), getAgent: vi.fn(), updateAgent: vi.fn() },
}))

const company = (name: string) => ({ id: 'c1', name }) as Company
const agent = { max_tokens: 500 } as AgentSettings

const wrapper = () => queryWrapper().Wrapper

describe('useCompanySettings', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: 'token', hasHydrated: true })
    vi.mocked(authService.getCurrentUser).mockResolvedValue({ company_id: 'c1', is_superuser: false } as User)
    vi.mocked(companyService.getAgent).mockResolvedValue(agent)
  })

  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
    useAuthStore.setState({ token: null, hasHydrated: false })
  })

  it('expõe o erro do backend quando a Company não carrega', async () => {
    vi.mocked(companyService.get).mockRejectedValue(new HttpError(500, 'Falha ao carregar a empresa'))

    const { result } = renderHook(() => useCompanySettings(), { wrapper: wrapper() })

    await waitFor(() => expect(result.current.error).toBe('Falha ao carregar a empresa'))
    expect(result.current.loading).toBe(false)
    expect(result.current.company).toBeNull()
  })

  it('refaz a leitura da Company depois de salvar, sem reload', async () => {
    vi.mocked(companyService.get).mockResolvedValueOnce(company('Antes')).mockResolvedValue(company('Depois'))
    vi.mocked(companyService.update).mockResolvedValue(company('Depois'))

    const { result } = renderHook(() => useCompanySettings(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.company?.name).toBe('Antes'))

    let saved: Awaited<ReturnType<typeof result.current.saveCompany>> | undefined
    await act(async () => {
      saved = await result.current.saveCompany({ name: 'Depois' })
    })

    expect(saved?.ok).toBe(true)
    expect(companyService.get).toHaveBeenCalledTimes(2)
    await waitFor(() => expect(result.current.company?.name).toBe('Depois'))
  })

  it('devolve os erros por campo quando o save falha com 422', async () => {
    vi.mocked(companyService.get).mockResolvedValue(company('Antes'))
    vi.mocked(companyService.update).mockRejectedValue(new HttpError(422, 'inválido', { email: 'Email inválido' }))

    const { result } = renderHook(() => useCompanySettings(), { wrapper: wrapper() })
    await waitFor(() => expect(result.current.company).not.toBeNull())

    let saved: Awaited<ReturnType<typeof result.current.saveCompany>> | undefined
    await act(async () => {
      saved = await result.current.saveCompany({ email: 'x' })
    })

    expect(saved).toEqual({ ok: false, fieldErrors: { email: 'Email inválido', _form: 'inválido' } })
    expect(companyService.get).toHaveBeenCalledTimes(1)
  })
})
