'use client'

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCurrentUser } from '@/hooks/useCurrentUser'
import { useSessionReady } from '@/hooks/useSessionReady'
import { queryKeys } from '@/lib/queryKeys'
import { HttpError } from '@/services/http'
import { gatewayService } from '@/services/gatewayService'
import {
  DEFAULT_GATEWAY_TIMEOUT_SECONDS,
  originChanged,
  type Gateway,
  type GatewayAssignment,
  type GatewayModel,
  type ProbeResult,
} from '@/types/gateway'
import { needsKeyForNewOrigin, type GatewayDraft, type ModelDraft } from './drafts'

const NO_GATEWAYS: Gateway[] = []
const NO_ASSIGNMENTS: GatewayAssignment[] = []

export function useGatewaysController() {
  const queryClient = useQueryClient()
  const sessionReady = useSessionReady()
  const profile = useCurrentUser()
  // `null` até o perfil chegar. As leituras de Gateways são só de superusuário (o backend responde 403 aos
  // demais), então só disparam com o perfil confirmado: usuário comum nunca faz essas chamadas.
  const isSuperuser = profile.data?.is_superuser ?? null
  const enabled = sessionReady && isSuperuser === true
  const gatewaysQuery = useQuery({ queryKey: queryKeys.gatewayList, queryFn: gatewayService.list, enabled })
  const assignmentsQuery = useQuery({
    queryKey: queryKeys.gatewayAssignments,
    queryFn: gatewayService.assignments,
    enabled,
  })
  const gateways = gatewaysQuery.data ?? NO_GATEWAYS
  const assignments = assignmentsQuery.data ?? NO_ASSIGNMENTS
  const loadError = profile.error ?? gatewaysQuery.error ?? assignmentsQuery.error
  // Sem acesso: perfil sem `is_superuser`, ou um 403 que escapou (perfil desatualizado). Vira estado próprio do
  // painel, não banner de erro.
  const restricted = isSuperuser === false || (loadError instanceof HttpError && loadError.status === 403)
  const loading =
    !restricted && !loadError && (isSuperuser === null || gatewaysQuery.isPending || assignmentsQuery.isPending)
  const [actionError, setActionError] = useState<string | null>(null)
  const error =
    actionError ??
    (loadError && !restricted ? (loadError instanceof Error ? loadError.message : 'Falha ao carregar gateways') : null)
  const setError = setActionError
  const [gatewayDraft, setGatewayDraft] = useState<GatewayDraft | null>(null)
  const [modelDraft, setModelDraft] = useState<ModelDraft | null>(null)
  const [remoteModels, setRemoteModels] = useState<Record<string, string[]>>({})
  const [probes, setProbes] = useState<Record<string, ProbeResult | 'running'>>({})
  const [saving, setSaving] = useState(false)
  const [forbidden, setForbidden] = useState(false)
  const [gatewayErrors, setGatewayErrors] = useState<Record<string, string>>({})
  const [modelErrors, setModelErrors] = useState<Record<string, string>>({})
  const readOnly = restricted || forbidden

  const reload = () => queryClient.invalidateQueries({ queryKey: queryKeys.gateways })

  /** Mostra o erro no banner. 403 vira modo somente leitura (a mensagem fica no aviso fixo). */
  const reportError = (e: unknown, fallback: string) => {
    if (e instanceof HttpError && e.status === 403) {
      setForbidden(true)
      setGatewayDraft(null)
      setModelDraft(null)
      setError(null)
      return
    }
    setError(e instanceof Error ? e.message : fallback)
  }

  /** Executa uma mutação. Um 422 com campo vai para `onFieldErrors` (erro junto ao campo), não para o banner. */
  const run = async (
    action: () => Promise<unknown>,
    onFieldErrors?: (errors: Record<string, string>) => void
  ) => {
    setSaving(true)
    setError(null)
    try {
      await action()
      await reload()
      return true
    } catch (e) {
      if (e instanceof HttpError && e.status === 422 && onFieldErrors && Object.keys(e.fieldErrors).length > 0) {
        onFieldErrors(e.fieldErrors)
      } else {
        reportError(e, 'Falha na operação')
      }
      return false
    } finally {
      setSaving(false)
    }
  }

  const patchGateway = (patch: Partial<GatewayDraft>) => {
    setGatewayDraft((draft) => (draft ? { ...draft, ...patch } : draft))
    setGatewayErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([field]) => !(field in patch))))
  }

  const patchModel = (patch: Partial<ModelDraft>) => {
    setModelDraft((draft) => (draft ? { ...draft, ...patch } : draft))
    setModelErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([field]) => !(field in patch))))
  }

  const saveGateway = async () => {
    if (!gatewayDraft || needsKeyForNewOrigin(gatewayDraft)) return
    const { id, name, base_url, api_key, clearKey, timeout_seconds, is_active } = gatewayDraft
    setGatewayErrors({})
    const ok = await run(() => {
      if (!id) {
        return gatewayService.create({ name, base_url, api_key: api_key || undefined, timeout_seconds, is_active })
      }
      // undefined mantém a chave salva; '' remove; texto substitui. Mudar a origem exige uma das duas últimas
      // (needsKeyForNewOrigin), então a chave salva nunca segue para outro endereço.
      const key = api_key ? api_key : clearKey ? '' : undefined
      return gatewayService.update(id, { name, base_url, api_key: key, timeout_seconds, is_active })
    }, setGatewayErrors)
    if (ok) setGatewayDraft(null)
  }

  const saveModel = async () => {
    if (!modelDraft) return
    const { id, gateway_id, ...data } = modelDraft
    setModelErrors({})
    const ok = await run(
      () => (id ? gatewayService.updateModel(id, data) : gatewayService.createModel(gateway_id, data)),
      setModelErrors
    )
    if (ok) setModelDraft(null)
  }

  const removeGateway = (g: Gateway) => {
    if (!window.confirm(`Remover o gateway "${g.name}" e seus ${g.models.length} modelo(s)?`)) return
    run(() => gatewayService.remove(g.id))
  }

  const removeModel = (m: GatewayModel) => {
    if (!window.confirm(`Remover o modelo "${m.name}"?`)) return
    run(() => gatewayService.removeModel(m.id))
  }

  const loadRemote = async (g: Gateway) => {
    try {
      const { models } = await gatewayService.remoteModels(g.id)
      setRemoteModels((prev) => ({ ...prev, [g.id]: models }))
    } catch (e) {
      reportError(e, 'Falha ao consultar modelos do gateway')
    }
  }

  const probe = async (m: GatewayModel) => {
    setProbes((prev) => ({ ...prev, [m.id]: 'running' }))
    try {
      const result = await gatewayService.testModel(m.id)
      setProbes((prev) => ({ ...prev, [m.id]: result }))
    } catch (e) {
      if (e instanceof HttpError && e.status === 403) {
        setProbes((prev) => Object.fromEntries(Object.entries(prev).filter(([id]) => id !== m.id)))
        reportError(e, 'Falha')
        return
      }
      setProbes((prev) => ({ ...prev, [m.id]: { ok: false, error: e instanceof Error ? e.message : 'Falha' } }))
    }
  }

  const openNewGateway = () => {
    setGatewayErrors({})
    setGatewayDraft({
      name: '',
      base_url: '',
      api_key: '',
      hasStoredKey: false,
      clearKey: false,
      timeout_seconds: DEFAULT_GATEWAY_TIMEOUT_SECONDS,
      is_active: true,
    })
  }

  const openEditGateway = (g: Gateway) => {
    setGatewayErrors({})
    setGatewayDraft({
      id: g.id,
      name: g.name,
      base_url: g.base_url,
      originalBaseUrl: g.base_url,
      api_key: '',
      hasStoredKey: g.has_api_key,
      clearKey: false,
      timeout_seconds: g.timeout_seconds,
      is_active: g.is_active,
    })
  }

  const openNewModel = (g: Gateway) => {
    setModelErrors({})
    setModelDraft({
      gateway_id: g.id,
      name: '',
      model_id: '',
      reasoning_effort: null,
      max_tokens: null,
      temperature: null,
      supports_tools: true,
      is_active: true,
    })
  }

  const openEditModel = (m: GatewayModel) => {
    setModelErrors({})
    setModelDraft({ ...m })
  }

  const activeModels = gateways
    .filter((g) => g.is_active)
    .flatMap((g) => g.models.filter((m) => m.is_active).map((m) => ({ ...m, gatewayName: g.name })))

  const keyRequired = gatewayDraft ? needsKeyForNewOrigin(gatewayDraft) : false
  const originMoved = gatewayDraft?.id ? originChanged(gatewayDraft.base_url, gatewayDraft.originalBaseUrl) : false

  return {
    gateways,
    assignments,
    loading,
    error,
    gatewayDraft,
    setGatewayDraft,
    modelDraft,
    setModelDraft,
    remoteModels,
    probes,
    saving,
    readOnly,
    restricted,
    gatewayErrors,
    modelErrors,
    run,
    patchGateway,
    patchModel,
    saveGateway,
    saveModel,
    removeGateway,
    removeModel,
    loadRemote,
    probe,
    openNewGateway,
    openEditGateway,
    openNewModel,
    openEditModel,
    activeModels,
    keyRequired,
    originMoved,
  }
}
