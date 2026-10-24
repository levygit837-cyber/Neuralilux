'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCurrentUser } from '@/hooks/useCurrentUser'
import { queryKeys } from '@/lib/queryKeys'
import { companyService } from '@/services/companyService'
import { HttpError } from '@/services/http'
import type { AgentSettings, Company } from '@/types/company'

export type SaveResult<T> = { ok: true; value: T } | { ok: false; fieldErrors: Record<string, string> }

const messageOf = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

function toSaveError(e: unknown): { ok: false; fieldErrors: Record<string, string> } {
  if (e instanceof HttpError && e.status === 422) {
    return { ok: false, fieldErrors: { ...e.fieldErrors, _form: e.message } }
  }
  return { ok: false, fieldErrors: { _form: messageOf(e, 'Falha ao salvar') } }
}

/**
 * Company e Agent do usuário logado, sempre lidos do backend (nada fica em localStorage).
 * `saveCompany` e `saveAgent` devolvem os erros de validação por campo, sem lançar, e
 * invalidam a query do recurso para a tela refletir o que o backend gravou.
 */
export type CompanySettingsState = ReturnType<typeof useCompanySettings>

export function useCompanySettings() {
  const queryClient = useQueryClient()
  const me = useCurrentUser()
  const companyId = me.data?.company_id ?? null

  const companyQuery = useQuery({
    queryKey: queryKeys.company(companyId ?? ''),
    queryFn: () => companyService.get(companyId as string),
    enabled: Boolean(companyId),
  })
  const agentQuery = useQuery({
    queryKey: queryKeys.agent(companyId ?? ''),
    // Company sem Agent (404) ainda edita os dados da empresa.
    queryFn: () =>
      companyService.getAgent(companyId as string).catch((e) => {
        if (e instanceof HttpError && e.status === 404) return null
        throw e
      }),
    enabled: Boolean(companyId),
  })

  const companyMutation = useMutation({
    mutationFn: (body: Parameters<typeof companyService.update>[1]) =>
      companyService.update(companyId as string, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.company(companyId as string) }),
  })
  const agentMutation = useMutation({
    mutationFn: (body: Partial<AgentSettings>) => companyService.updateAgent(companyId as string, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.agent(companyId as string) }),
  })

  const noCompany = <T,>() => Promise.resolve<SaveResult<T>>({ ok: false, fieldErrors: { _form: 'Empresa não carregada' } })

  const saveCompany = async (body: Parameters<typeof companyService.update>[1]): Promise<SaveResult<Company>> => {
    if (!companyId) return noCompany()
    try {
      return { ok: true, value: await companyMutation.mutateAsync(body) }
    } catch (e) {
      return toSaveError(e)
    }
  }

  const saveAgent = async (body: Partial<AgentSettings>): Promise<SaveResult<AgentSettings>> => {
    if (!companyId) return noCompany()
    try {
      return { ok: true, value: await agentMutation.mutateAsync(body) }
    } catch (e) {
      return toSaveError(e)
    }
  }

  const loadError = me.error ?? companyQuery.error ?? agentQuery.error
  const missingCompany = me.isSuccess && !me.data.company_id
  return {
    company: companyQuery.data ?? null,
    agent: agentQuery.data ?? null,
    loading: !missingCompany && !loadError && (me.isPending || companyQuery.isPending || agentQuery.isPending),
    /** Falha ao carregar (sem Company, 403, rede). */
    error: missingCompany
      ? 'Seu usuário não está vinculado a uma empresa.'
      : loadError
        ? messageOf(loadError, 'Falha ao carregar')
        : null,
    saveCompany,
    saveAgent,
  }
}
