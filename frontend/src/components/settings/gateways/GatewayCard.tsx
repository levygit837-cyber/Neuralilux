import { Plus, Trash2, Pencil, Play, Download, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { Gateway, GatewayModel, ProbeResult } from '@/types/gateway'

interface GatewayCardProps {
  gateway: Gateway
  readOnly: boolean
  probes: Record<string, ProbeResult | 'running'>
  remoteModels?: string[]
  onEditGateway: (g: Gateway) => void
  onRemoveGateway: (g: Gateway) => void
  onAddModel: (g: Gateway) => void
  onEditModel: (m: GatewayModel) => void
  onRemoveModel: (m: GatewayModel) => void
  onProbe: (m: GatewayModel) => void
  onLoadRemote: (g: Gateway) => void
}

export function GatewayCard({
  gateway: g,
  readOnly,
  probes,
  remoteModels,
  onEditGateway,
  onRemoveGateway,
  onAddModel,
  onEditModel,
  onRemoveModel,
  onProbe,
  onLoadRemote,
}: GatewayCardProps) {
  return (
    <section className="rounded-2xl border border-brand-border bg-brand-card p-6" aria-label={`Gateway ${g.name}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="flex items-center gap-2 text-base font-semibold text-content-light">
            {g.name}
            {!g.is_active && (
              <span className="rounded-full bg-brand-hover px-2 py-0.5 text-xs font-normal text-content-gray">inativo</span>
            )}
          </h3>
          <p className="truncate font-mono text-xs text-content-gray">{g.base_url}</p>
          <p className="mt-1 flex items-center gap-1 text-xs text-content-gray">
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
            onClick={() => onEditGateway(g)}
          >
            <Pencil className="h-4 w-4" aria-hidden />
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={readOnly}
            aria-label={`Remover gateway ${g.name}`}
            onClick={() => onRemoveGateway(g)}
          >
            <Trash2 className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </div>

      <ul className="mt-4 divide-y divide-brand-border">
        {g.models.map((m) => {
          const result = probes[m.id]
          return (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-content-light">
                  {m.name}
                  {!m.is_active && <span className="ml-2 text-xs font-normal text-content-gray">(inativo)</span>}
                </p>
                <p className="font-mono text-xs text-content-gray">
                  {m.model_id}
                  {m.reasoning_effort ? ` · effort ${m.reasoning_effort}` : ''}
                  {m.supports_tools ? '' : ' · sem ferramentas'}
                </p>
                {result && (
                  <p
                    role="status"
                    className={`mt-1 text-xs ${result === 'running' ? 'text-content-gray' : result.ok ? 'text-status-success' : 'text-status-error'}`}
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
                  onClick={() => onProbe(m)}
                >
                  <Play className="h-4 w-4" aria-hidden />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={readOnly}
                  aria-label={`Editar ${m.name}`}
                  onClick={() => onEditModel(m)}
                >
                  <Pencil className="h-4 w-4" aria-hidden />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={readOnly}
                  aria-label={`Remover ${m.name}`}
                  onClick={() => onRemoveModel(m)}
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </Button>
              </div>
            </li>
          )
        })}
      </ul>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => onAddModel(g)}>
          <Plus className="h-4 w-4" aria-hidden /> Adicionar modelo
        </Button>
        <Button variant="secondary" size="sm" disabled={readOnly} onClick={() => onLoadRemote(g)}>
          <Download className="h-4 w-4" aria-hidden /> Buscar modelos do gateway
        </Button>
      </div>
      {remoteModels && (
        <p className="mt-2 text-xs text-content-gray">
          Disponíveis: {remoteModels.length ? remoteModels.join(', ') : 'nenhum'}
        </p>
      )}
    </section>
  )
}
