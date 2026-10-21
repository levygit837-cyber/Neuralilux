'use client'

import { useCallback, useEffect, useState } from 'react'
import { Network, Plus, Trash2, Pencil, Play, Download, KeyRound, Lock } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { authService } from '@/services/authService'
import { GatewayApiError, gatewayService } from '@/services/gatewayService'
import { useAuthStore } from '@/stores/useAuthStore'
import {
  AGENT_LABELS,
  AGENT_TYPES,
  DEFAULT_GATEWAY_TIMEOUT_SECONDS,
  originChanged,
  type Gateway,
  type GatewayAssignment,
  type GatewayModel,
  type GatewayModelInput,
  type ProbeResult,
  type ReasoningEffort,
} from '@/types/gateway'

const EFFORTS: { value: ReasoningEffort | ''; label: string }[] = [
  { value: '', label: 'Padrão do modelo' },
  { value: 'low', label: 'Baixo' },
  { value: 'medium', label: 'Médio' },
  { value: 'high', label: 'Alto' },
]

const fieldLabel = 'mb-1.5 block text-xs font-medium text-text-gray'
const selectClass =
  'h-12 w-full rounded-md border border-border-color bg-dark px-3 text-sm text-text-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'

const READ_ONLY_MESSAGE = 'Somente administradores podem alterar Gateways'
const ORIGIN_KEY_MESSAGE =
  'Você mudou a origem (esquema, host ou porta). A chave salva não é enviada para outro endereço: ' +
  'informe a chave deste endereço ou marque a opção abaixo.'

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null
  return (
    <p id={id} role="alert" className="mt-1.5 text-xs text-red-300">
      {message}
    </p>
  )
}

interface GatewayDraft {
  id?: string
  name: string
  base_url: string
  /** URL salva ao abrir a edição; base para detectar a troca de origem. */
  originalBaseUrl?: string
  api_key: string
  hasStoredKey: boolean
  clearKey: boolean
  timeout_seconds: number
  is_active: boolean
}

interface ModelDraft extends GatewayModelInput {
  id?: string
  gateway_id: string
}

/** Edição que mudou a origem sem decisão explícita sobre a chave (informar uma nova ou marcar que não há chave). */
function needsKeyForNewOrigin(draft: GatewayDraft): boolean {
  return Boolean(draft.id) && !draft.api_key && !draft.clearKey && originChanged(draft.base_url, draft.originalBaseUrl)
}

export function GatewaysPanel() {
  const [gateways, setGateways] = useState<Gateway[]>([])
  const [assignments, setAssignments] = useState<GatewayAssignment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [gatewayDraft, setGatewayDraft] = useState<GatewayDraft | null>(null)
  const [modelDraft, setModelDraft] = useState<ModelDraft | null>(null)
  const [remoteModels, setRemoteModels] = useState<Record<string, string[]>>({})
  const [probes, setProbes] = useState<Record<string, ProbeResult | 'running'>>({})
  const [saving, setSaving] = useState(false)
  const token = useAuthStore((state) => state.token)
  const [isSuperuser, setIsSuperuser] = useState<boolean | null>(null)
  const [forbidden, setForbidden] = useState(false)
  const [gatewayErrors, setGatewayErrors] = useState<Record<string, string>>({})
  const [modelErrors, setModelErrors] = useState<Record<string, string>>({})
  // `is_superuser` desconhecido (null): a trava fica por conta do 403 do backend.
  const readOnly = isSuperuser === false || forbidden

  const reload = useCallback(async () => {
    try {
      const [g, a] = await Promise.all([gatewayService.list(), gatewayService.assignments()])
      setGateways(g)
      setAssignments(a)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha ao carregar gateways')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    authService
      .getCurrentUser(token)
      .then((me) => {
        if (!cancelled) setIsSuperuser(me.is_superuser)
      })
      .catch(() => {
        /* sem o perfil, vale o 403 do backend */
      })
    return () => {
      cancelled = true
    }
  }, [token])

  /** Mostra o erro no banner. 403 vira modo somente leitura (a mensagem fica no aviso fixo). */
  const reportError = (e: unknown, fallback: string) => {
    if (e instanceof GatewayApiError && e.status === 403) {
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
      if (e instanceof GatewayApiError && e.status === 422 && onFieldErrors && Object.keys(e.fieldErrors).length > 0) {
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
      if (e instanceof GatewayApiError && e.status === 403) {
        setProbes((prev) => Object.fromEntries(Object.entries(prev).filter(([id]) => id !== m.id)))
        reportError(e, 'Falha')
        return
      }
      setProbes((prev) => ({ ...prev, [m.id]: { ok: false, error: e instanceof Error ? e.message : 'Falha' } }))
    }
  }

  const activeModels = gateways
    .filter((g) => g.is_active)
    .flatMap((g) => g.models.filter((m) => m.is_active).map((m) => ({ ...m, gatewayName: g.name })))

  const keyRequired = gatewayDraft ? needsKeyForNewOrigin(gatewayDraft) : false
  const originMoved = gatewayDraft?.id ? originChanged(gatewayDraft.base_url, gatewayDraft.originalBaseUrl) : false

  return (
    <div className="space-y-6">
      {error && (
        <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {readOnly && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-xl border border-border-color bg-hover px-4 py-3 text-sm text-text-gray"
        >
          <Lock className="h-4 w-4 shrink-0" aria-hidden />
          {READ_ONLY_MESSAGE}. Você pode consultar, mas não editar nem testar.
        </p>
      )}

      {/* Atribuição por agente */}
      <section className="rounded-2xl border border-border-color bg-card p-7" aria-labelledby="gw-assign">
        <div className="mb-6 flex items-center gap-4">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
            <Network className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h3 id="gw-assign" className="text-lg font-semibold text-text-light">Modelo de cada agente</h3>
            <p className="text-sm text-text-gray">
              Cada agente usa o modelo de um Gateway. O tipo Padrão vale para o agente que não tem modelo próprio.
            </p>
          </div>
        </div>
        <div className="space-y-4">
          {AGENT_TYPES.map((agent) => (
            <div key={agent} className="grid items-center gap-3 md:grid-cols-[1fr_1.4fr]">
              <label htmlFor={`assign-${agent}`}>
                <span className="block text-sm font-medium text-text-light">{AGENT_LABELS[agent].title}</span>
                <span className="block text-xs text-text-gray">{AGENT_LABELS[agent].hint}</span>
              </label>
              <select
                id={`assign-${agent}`}
                className={selectClass}
                disabled={saving || loading || readOnly}
                value={assignments.find((a) => a.agent_type === agent)?.gateway_model_id ?? ''}
                onChange={(e) =>
                  run(() =>
                    e.target.value
                      ? gatewayService.assign(agent, e.target.value)
                      : gatewayService.unassign(agent)
                  )
                }
              >
                <option value="">Sem modelo atribuído</option>
                {activeModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.gatewayName} · {m.name}
                  </option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </section>

      {/* Lista de gateways */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-light">Gateways</h2>
        <Button
          size="sm"
          disabled={readOnly}
          onClick={() => {
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
          }}
        >
          <Plus className="h-4 w-4" aria-hidden /> Novo gateway
        </Button>
      </div>

      {loading && <p className="text-sm text-text-gray">Carregando…</p>}
      {!loading && gateways.length === 0 && (
        <p className="rounded-xl border border-dashed border-border-color p-6 text-center text-sm text-text-gray">
          Nenhum gateway cadastrado. Adicione a URL de um Gateway que fale o protocolo Anthropic Messages.
        </p>
      )}

      {gateways.map((g) => (
        <section key={g.id} className="rounded-2xl border border-border-color bg-card p-6" aria-label={`Gateway ${g.name}`}>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="flex items-center gap-2 text-base font-semibold text-text-light">
                {g.name}
                {!g.is_active && (
                  <span className="rounded-full bg-hover px-2 py-0.5 text-xs font-normal text-text-gray">inativo</span>
                )}
              </h3>
              <p className="truncate font-mono text-xs text-text-gray">{g.base_url}</p>
              <p className="mt-1 flex items-center gap-1 text-xs text-text-gray">
                <KeyRound className="h-3 w-3" aria-hidden />
                {g.has_api_key ? 'Chave de API salva (não exibida)' : 'Sem chave de API'}
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={readOnly}
                aria-label={`Editar gateway ${g.name}`}
                onClick={() => {
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
                }}
              >
                <Pencil className="h-4 w-4" aria-hidden />
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={readOnly}
                aria-label={`Remover gateway ${g.name}`}
                onClick={() => removeGateway(g)}
              >
                <Trash2 className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          </div>

          <ul className="mt-4 divide-y divide-border-color">
            {g.models.map((m) => {
              const result = probes[m.id]
              return (
                <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-text-light">
                      {m.name}
                      {!m.is_active && <span className="ml-2 text-xs font-normal text-text-gray">(inativo)</span>}
                    </p>
                    <p className="font-mono text-xs text-text-gray">
                      {m.model_id}
                      {m.reasoning_effort ? ` · effort ${m.reasoning_effort}` : ''}
                      {m.supports_tools ? '' : ' · sem ferramentas'}
                    </p>
                    {result && (
                      <p
                        role="status"
                        className={`mt-1 text-xs ${result === 'running' ? 'text-text-gray' : result.ok ? 'text-green-400' : 'text-red-300'}`}
                      >
                        {result === 'running'
                          ? 'Testando…'
                          : result.ok
                            ? `OK em ${result.latency_ms} ms: "${(result.content ?? '').slice(0, 60)}"`
                            : result.error}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={readOnly}
                      aria-label={`Testar ${m.name}`}
                      onClick={() => probe(m)}
                    >
                      <Play className="h-4 w-4" aria-hidden />
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={readOnly}
                      aria-label={`Editar ${m.name}`}
                      onClick={() => {
                        setModelErrors({})
                        setModelDraft({ ...m })
                      }}
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={readOnly}
                      aria-label={`Remover ${m.name}`}
                      onClick={() => removeModel(m)}
                    >
                      <Trash2 className="h-4 w-4" aria-hidden />
                    </Button>
                  </div>
                </li>
              )
            })}
          </ul>

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={readOnly}
              onClick={() => {
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
              }}
            >
              <Plus className="h-4 w-4" aria-hidden /> Adicionar modelo
            </Button>
            <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => loadRemote(g)}>
              <Download className="h-4 w-4" aria-hidden /> Buscar modelos do gateway
            </Button>
          </div>
          {remoteModels[g.id] && (
            <p className="mt-2 text-xs text-text-gray">
              Disponíveis: {remoteModels[g.id].length ? remoteModels[g.id].join(', ') : 'nenhum'}
            </p>
          )}
        </section>
      ))}

      {/* Formulário de gateway */}
      {gatewayDraft && (
        <form
          className="space-y-4 rounded-2xl border border-primary/50 bg-card p-6"
          aria-label={gatewayDraft.id ? 'Editar gateway' : 'Novo gateway'}
          onSubmit={(e) => {
            e.preventDefault()
            saveGateway()
          }}
        >
          <h3 className="text-base font-semibold text-text-light">
            {gatewayDraft.id ? 'Editar gateway' : 'Novo gateway'}
          </h3>
          <div>
            <label className={fieldLabel} htmlFor="gw-name">Nome</label>
            <Input id="gw-name" required value={gatewayDraft.name} placeholder="Kiro-backend"
              aria-invalid={Boolean(gatewayErrors.name)}
              aria-describedby={gatewayErrors.name ? 'gw-name-error' : undefined}
              onChange={(e) => patchGateway({ name: e.target.value })} />
            <FieldError id="gw-name-error" message={gatewayErrors.name} />
          </div>
          <div>
            <label className={fieldLabel} htmlFor="gw-url">URL base (raiz, sem /v1)</label>
            <Input id="gw-url" required type="url" value={gatewayDraft.base_url} placeholder="http://localhost:5580"
              aria-invalid={Boolean(gatewayErrors.base_url)}
              aria-describedby={gatewayErrors.base_url ? 'gw-url-hint gw-url-error' : 'gw-url-hint'}
              onChange={(e) => patchGateway({ base_url: e.target.value })} />
            <p id="gw-url-hint" className="mt-1.5 text-xs text-text-muted">
              O cliente acrescenta /v1/messages a esta URL.
            </p>
            <FieldError id="gw-url-error" message={gatewayErrors.base_url} />
          </div>
          <div>
            <label className={fieldLabel} htmlFor="gw-key">Chave de API (opcional)</label>
            <Input id="gw-key" type="password" autoComplete="off" value={gatewayDraft.api_key}
              placeholder={gatewayDraft.hasStoredKey ? 'Salva. Digite para substituir' : 'sk-…'}
              aria-invalid={keyRequired || Boolean(gatewayErrors.api_key)}
              aria-describedby={
                keyRequired ? 'gw-key-reason' : gatewayErrors.api_key ? 'gw-key-error' : undefined
              }
              onChange={(e) => patchGateway({ api_key: e.target.value })} />
            {keyRequired && (
              <p id="gw-key-reason" role="alert" className="mt-1.5 text-xs text-red-300">
                {ORIGIN_KEY_MESSAGE}
              </p>
            )}
            <FieldError id="gw-key-error" message={gatewayErrors.api_key} />
            {(gatewayDraft.hasStoredKey || originMoved) && (
              <label className="mt-2 flex items-center gap-2 text-xs text-text-gray">
                <input type="checkbox" checked={gatewayDraft.clearKey}
                  onChange={(e) => patchGateway({ clearKey: e.target.checked })} />
                {gatewayDraft.hasStoredKey ? 'Remover a chave salva' : 'Este endereço não usa chave de API'}
              </label>
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className={fieldLabel} htmlFor="gw-timeout">Timeout (segundos)</label>
              <Input id="gw-timeout" type="number" min={1} max={900} value={gatewayDraft.timeout_seconds}
                aria-invalid={Boolean(gatewayErrors.timeout_seconds)}
                aria-describedby={gatewayErrors.timeout_seconds ? 'gw-timeout-error' : undefined}
                onChange={(e) =>
                  patchGateway({ timeout_seconds: Number(e.target.value) || DEFAULT_GATEWAY_TIMEOUT_SECONDS })
                } />
              <FieldError id="gw-timeout-error" message={gatewayErrors.timeout_seconds} />
            </div>
            <label className="flex items-center gap-2 self-end pb-3 text-sm text-text-light">
              <input type="checkbox" checked={gatewayDraft.is_active}
                onChange={(e) => patchGateway({ is_active: e.target.checked })} />
              Ativo
            </label>
          </div>
          <div className="flex gap-3">
            <Button
              type="submit"
              disabled={saving || keyRequired}
              aria-describedby={keyRequired ? 'gw-key-reason' : undefined}
            >
              Salvar
            </Button>
            <Button type="button" variant="secondary" onClick={() => setGatewayDraft(null)}>Cancelar</Button>
          </div>
        </form>
      )}

      {/* Formulário de modelo */}
      {modelDraft && (
        <form
          className="space-y-4 rounded-2xl border border-primary/50 bg-card p-6"
          aria-label={modelDraft.id ? 'Editar modelo' : 'Novo modelo'}
          onSubmit={(e) => {
            e.preventDefault()
            saveModel()
          }}
        >
          <h3 className="text-base font-semibold text-text-light">
            {modelDraft.id ? 'Editar modelo' : 'Novo modelo'}
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className={fieldLabel} htmlFor="gm-name">Nome na lista</label>
              <Input id="gm-name" required value={modelDraft.name} placeholder="Sonnet 5.5 (low)"
                aria-invalid={Boolean(modelErrors.name)}
                aria-describedby={modelErrors.name ? 'gm-name-error' : undefined}
                onChange={(e) => patchModel({ name: e.target.value })} />
              <FieldError id="gm-name-error" message={modelErrors.name} />
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-id">ID do modelo no gateway</label>
              <Input id="gm-id" required list="gm-remote" value={modelDraft.model_id} placeholder="claude-sonnet-5.5"
                aria-invalid={Boolean(modelErrors.model_id)}
                aria-describedby={modelErrors.model_id ? 'gm-id-error' : undefined}
                onChange={(e) => patchModel({ model_id: e.target.value })} />
              <datalist id="gm-remote">
                {(remoteModels[modelDraft.gateway_id] ?? []).map((id) => (
                  <option key={id} value={id} />
                ))}
              </datalist>
              <FieldError id="gm-id-error" message={modelErrors.model_id} />
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-effort">Esforço de raciocínio</label>
              <select id="gm-effort" className={selectClass} value={modelDraft.reasoning_effort ?? ''}
                aria-invalid={Boolean(modelErrors.reasoning_effort)}
                aria-describedby={modelErrors.reasoning_effort ? 'gm-effort-error' : undefined}
                onChange={(e) => patchModel({ reasoning_effort: (e.target.value || null) as ReasoningEffort | null })}>
                {EFFORTS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
              <FieldError id="gm-effort-error" message={modelErrors.reasoning_effort} />
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-max">Máx. de tokens (vazio = padrão)</label>
              <Input id="gm-max" type="number" min={1} value={modelDraft.max_tokens ?? ''}
                aria-invalid={Boolean(modelErrors.max_tokens)}
                aria-describedby={modelErrors.max_tokens ? 'gm-max-error' : undefined}
                onChange={(e) =>
                  patchModel({ max_tokens: e.target.value.trim() === '' ? null : Number(e.target.value) })
                } />
              <FieldError id="gm-max-error" message={modelErrors.max_tokens} />
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-temp">Temperatura (vazio = padrão)</label>
              <Input id="gm-temp" type="number" min={0} max={2} step={0.1} value={modelDraft.temperature ?? ''}
                aria-invalid={Boolean(modelErrors.temperature)}
                aria-describedby={modelErrors.temperature ? 'gm-temp-error' : undefined}
                onChange={(e) =>
                  patchModel({ temperature: e.target.value.trim() === '' ? null : Number(e.target.value) })
                } />
              <FieldError id="gm-temp-error" message={modelErrors.temperature} />
            </div>
            <div className="flex flex-col justify-end gap-2 pb-3 text-sm text-text-light">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={modelDraft.supports_tools}
                  onChange={(e) => patchModel({ supports_tools: e.target.checked })} />
                Aceita ferramentas (function calling)
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={modelDraft.is_active}
                  onChange={(e) => patchModel({ is_active: e.target.checked })} />
                Ativo
              </label>
            </div>
          </div>
          <div className="flex gap-3">
            <Button type="submit" disabled={saving}>Salvar</Button>
            <Button type="button" variant="secondary" onClick={() => setModelDraft(null)}>Cancelar</Button>
          </div>
        </form>
      )}
    </div>
  )
}
