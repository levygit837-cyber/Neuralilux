'use client'

import { useCallback, useEffect, useState } from 'react'
import { Network, Plus, Trash2, Pencil, Play, Download, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { gatewayService } from '@/services/gatewayService'
import {
  AGENT_LABELS,
  AGENT_TYPES,
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

interface GatewayDraft {
  id?: string
  name: string
  base_url: string
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

  const run = async (action: () => Promise<unknown>) => {
    setSaving(true)
    setError(null)
    try {
      await action()
      await reload()
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Falha na operação')
      return false
    } finally {
      setSaving(false)
    }
  }

  const saveGateway = async () => {
    if (!gatewayDraft) return
    const { id, name, base_url, api_key, clearKey, timeout_seconds, is_active } = gatewayDraft
    const ok = await run(() => {
      if (!id) {
        return gatewayService.create({ name, base_url, api_key: api_key || undefined, timeout_seconds, is_active })
      }
      // undefined mantém a chave salva; '' remove; texto substitui.
      const key = api_key ? api_key : clearKey ? '' : undefined
      return gatewayService.update(id, { name, base_url, api_key: key, timeout_seconds, is_active })
    })
    if (ok) setGatewayDraft(null)
  }

  const saveModel = async () => {
    if (!modelDraft) return
    const { id, gateway_id, ...data } = modelDraft
    const ok = await run(() =>
      id ? gatewayService.updateModel(id, data) : gatewayService.createModel(gateway_id, data)
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
      setError(e instanceof Error ? e.message : 'Falha ao consultar modelos do gateway')
    }
  }

  const probe = async (m: GatewayModel) => {
    setProbes((prev) => ({ ...prev, [m.id]: 'running' }))
    try {
      const result = await gatewayService.testModel(m.id)
      setProbes((prev) => ({ ...prev, [m.id]: result }))
    } catch (e) {
      setProbes((prev) => ({ ...prev, [m.id]: { ok: false, error: e instanceof Error ? e.message : 'Falha' } }))
    }
  }

  const activeModels = gateways
    .filter((g) => g.is_active)
    .flatMap((g) => g.models.filter((m) => m.is_active).map((m) => ({ ...m, gatewayName: g.name })))

  return (
    <div className="space-y-6">
      {error && (
        <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
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
                disabled={saving || loading}
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
          onClick={() =>
            setGatewayDraft({
              name: '',
              base_url: '',
              api_key: '',
              hasStoredKey: false,
              clearKey: false,
              timeout_seconds: 120,
              is_active: true,
            })
          }
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
                aria-label={`Editar gateway ${g.name}`}
                onClick={() =>
                  setGatewayDraft({
                    id: g.id,
                    name: g.name,
                    base_url: g.base_url,
                    api_key: '',
                    hasStoredKey: g.has_api_key,
                    clearKey: false,
                    timeout_seconds: g.timeout_seconds,
                    is_active: g.is_active,
                  })
                }
              >
                <Pencil className="h-4 w-4" aria-hidden />
              </Button>
              <Button variant="secondary" size="sm" aria-label={`Remover gateway ${g.name}`} onClick={() => removeGateway(g)}>
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
                    <Button variant="secondary" size="sm" aria-label={`Testar ${m.name}`} onClick={() => probe(m)}>
                      <Play className="h-4 w-4" aria-hidden />
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      aria-label={`Editar ${m.name}`}
                      onClick={() => setModelDraft({ ...m })}
                    >
                      <Pencil className="h-4 w-4" aria-hidden />
                    </Button>
                    <Button variant="secondary" size="sm" aria-label={`Remover ${m.name}`} onClick={() => removeModel(m)}>
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
              onClick={() =>
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
            >
              <Plus className="h-4 w-4" aria-hidden /> Adicionar modelo
            </Button>
            <Button variant="secondary" size="sm" onClick={() => loadRemote(g)}>
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
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, name: e.target.value })} />
          </div>
          <div>
            <label className={fieldLabel} htmlFor="gw-url">URL base (termina em /v1)</label>
            <Input id="gw-url" required type="url" value={gatewayDraft.base_url} placeholder="http://localhost:5580/v1"
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, base_url: e.target.value })} />
          </div>
          <div>
            <label className={fieldLabel} htmlFor="gw-key">Chave de API (opcional)</label>
            <Input id="gw-key" type="password" autoComplete="off" value={gatewayDraft.api_key}
              placeholder={gatewayDraft.hasStoredKey ? 'Salva. Digite para substituir' : 'sk-…'}
              onChange={(e) => setGatewayDraft({ ...gatewayDraft, api_key: e.target.value })} />
            {gatewayDraft.hasStoredKey && (
              <label className="mt-2 flex items-center gap-2 text-xs text-text-gray">
                <input type="checkbox" checked={gatewayDraft.clearKey}
                  onChange={(e) => setGatewayDraft({ ...gatewayDraft, clearKey: e.target.checked })} />
                Remover a chave salva
              </label>
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className={fieldLabel} htmlFor="gw-timeout">Timeout (segundos)</label>
              <Input id="gw-timeout" type="number" min={1} max={900} value={gatewayDraft.timeout_seconds}
                onChange={(e) => setGatewayDraft({ ...gatewayDraft, timeout_seconds: Number(e.target.value) || 120 })} />
            </div>
            <label className="flex items-center gap-2 self-end pb-3 text-sm text-text-light">
              <input type="checkbox" checked={gatewayDraft.is_active}
                onChange={(e) => setGatewayDraft({ ...gatewayDraft, is_active: e.target.checked })} />
              Ativo
            </label>
          </div>
          <div className="flex gap-3">
            <Button type="submit" disabled={saving}>Salvar</Button>
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
                onChange={(e) => setModelDraft({ ...modelDraft, name: e.target.value })} />
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-id">ID do modelo no gateway</label>
              <Input id="gm-id" required list="gm-remote" value={modelDraft.model_id} placeholder="claude-sonnet-5.5"
                onChange={(e) => setModelDraft({ ...modelDraft, model_id: e.target.value })} />
              <datalist id="gm-remote">
                {(remoteModels[modelDraft.gateway_id] ?? []).map((id) => (
                  <option key={id} value={id} />
                ))}
              </datalist>
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-effort">Esforço de raciocínio</label>
              <select id="gm-effort" className={selectClass} value={modelDraft.reasoning_effort ?? ''}
                onChange={(e) => setModelDraft({ ...modelDraft, reasoning_effort: (e.target.value || null) as ReasoningEffort | null })}>
                {EFFORTS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-max">Máx. de tokens (vazio = padrão)</label>
              <Input id="gm-max" type="number" min={1} value={modelDraft.max_tokens ?? ''}
                onChange={(e) =>
                  setModelDraft({ ...modelDraft, max_tokens: e.target.value.trim() === '' ? null : Number(e.target.value) })
                } />
            </div>
            <div>
              <label className={fieldLabel} htmlFor="gm-temp">Temperatura (vazio = padrão)</label>
              <Input id="gm-temp" type="number" min={0} max={2} step={0.1} value={modelDraft.temperature ?? ''}
                onChange={(e) =>
                  setModelDraft({ ...modelDraft, temperature: e.target.value.trim() === '' ? null : Number(e.target.value) })
                } />
            </div>
            <div className="flex flex-col justify-end gap-2 pb-3 text-sm text-text-light">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={modelDraft.supports_tools}
                  onChange={(e) => setModelDraft({ ...modelDraft, supports_tools: e.target.checked })} />
                Aceita ferramentas (function calling)
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={modelDraft.is_active}
                  onChange={(e) => setModelDraft({ ...modelDraft, is_active: e.target.checked })} />
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
