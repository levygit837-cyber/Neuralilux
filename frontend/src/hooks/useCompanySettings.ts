'use client'

import { useCallback, useEffect, useState } from 'react'
import { authService } from '@/services/authService'
import { companyService } from '@/services/companyService'
import { HttpError } from '@/services/http'
import { useAuthStore } from '@/stores/useAuthStore'
import type { AgentSettings, Company } from '@/types/company'

export type SaveResult<T> = { ok: true; value: T } | { ok: false; fieldErrors: Record<string, string> }

interface CompanyState {
  company: Company | null
  agent: AgentSettings | null
  loading: boolean
  /** Falha ao carregar (sem Company, 403, rede). */
  error: string | null
}

const messageOf = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

/**
 * Company e Agent do usuário logado, sempre lidos do backend (nada fica em localStorage).
 * `saveCompany` e `saveAgent` devolvem os erros de validação por campo, sem lançar.
 */
export type CompanySettingsState = ReturnType<typeof useCompanySettings>

export function useCompanySettings() {
  const token = useAuthStore((state) => state.token)
  const [state, setState] = useState<CompanyState>({ company: null, agent: null, loading: true, error: null })

  useEffect(() => {
    if (!token) return
    let cancelled = false
    const load = async () => {
      try {
        const me = await authService.getCurrentUser(token)
        if (!me.company_id) throw new Error('Seu usuário não está vinculado a uma empresa.')
        const [company, agent] = await Promise.all([
          companyService.get(me.company_id),
          // Company sem Agent (404) ainda edita os dados da empresa.
          companyService.getAgent(me.company_id).catch((e) => {
            if (e instanceof HttpError && e.status === 404) return null
            throw e
          }),
        ])
        if (!cancelled) setState({ company, agent, loading: false, error: null })
      } catch (e) {
        if (!cancelled) setState({ company: null, agent: null, loading: false, error: messageOf(e, 'Falha ao carregar') })
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token])

  const save = useCallback(async <T,>(action: () => Promise<T>, apply: (value: T) => void): Promise<SaveResult<T>> => {
    try {
      const value = await action()
      apply(value)
      return { ok: true, value }
    } catch (e) {
      if (e instanceof HttpError && e.status === 422) {
        return { ok: false, fieldErrors: { ...e.fieldErrors, _form: e.message } }
      }
      return { ok: false, fieldErrors: { _form: messageOf(e, 'Falha ao salvar') } }
    }
  }, [])

  const saveCompany = useCallback(
    (body: Parameters<typeof companyService.update>[1]) => {
      const id = state.company?.id
      if (!id) return Promise.resolve<SaveResult<Company>>({ ok: false, fieldErrors: { _form: 'Empresa não carregada' } })
      return save(() => companyService.update(id, body), (company) => setState((s) => ({ ...s, company })))
    },
    [save, state.company?.id]
  )

  const saveAgent = useCallback(
    (body: Partial<AgentSettings>) => {
      const id = state.company?.id
      if (!id) return Promise.resolve<SaveResult<AgentSettings>>({ ok: false, fieldErrors: { _form: 'Empresa não carregada' } })
      return save(() => companyService.updateAgent(id, body), (agent) => setState((s) => ({ ...s, agent })))
    },
    [save, state.company?.id]
  )

  return { ...state, saveCompany, saveAgent }
}
