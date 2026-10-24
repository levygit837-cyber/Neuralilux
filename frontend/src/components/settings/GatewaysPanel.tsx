'use client'

import { Plus, Lock } from '@phosphor-icons/react'
import { Button } from '@/components/ui/Button'
import { AssignmentsSection } from './gateways/AssignmentsSection'
import { READ_ONLY_MESSAGE, RESTRICTED_HINT, RESTRICTED_MESSAGE } from './gateways/constants'
import { GatewayCard } from './gateways/GatewayCard'
import { GatewayForm } from './gateways/GatewayForm'
import { ModelForm } from './gateways/ModelForm'
import { useGatewaysController } from './gateways/useGatewaysController'

export function GatewaysPanel() {
  const c = useGatewaysController()

  if (c.restricted) {
    return (
      <div
        role="status"
        className="flex items-start gap-3 rounded-xl border border-brand-border bg-brand-hover px-4 py-4 text-sm text-content-gray"
      >
        <Lock className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div>
          <p className="font-medium text-content-light">{RESTRICTED_MESSAGE}</p>
          <p className="mt-1">{RESTRICTED_HINT}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {c.error && (
        <div role="alert" className="rounded-xl border border-status-error/40 bg-status-error/10 px-4 py-3 text-sm text-status-error">
          {c.error}
        </div>
      )}

      {c.readOnly && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-xl border border-brand-border bg-brand-hover px-4 py-3 text-sm text-content-gray"
        >
          <Lock className="h-4 w-4 shrink-0" aria-hidden />
          {READ_ONLY_MESSAGE}. Suas alterações foram recusadas pelo servidor.
        </p>
      )}

      {/* Atribuição por agente */}
      <AssignmentsSection
        assignments={c.assignments}
        activeModels={c.activeModels}
        disabled={c.saving || c.loading || c.readOnly}
        run={c.run}
      />

      {/* Lista de gateways */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-content-light">Gateways</h2>
        <Button size="sm" disabled={c.readOnly} onClick={c.openNewGateway}>
          <Plus className="h-4 w-4" aria-hidden /> Novo gateway
        </Button>
      </div>

      {c.loading && <p className="text-sm text-content-gray">Carregando…</p>}
      {!c.loading && c.gateways.length === 0 && (
        <p className="rounded-xl border border-dashed border-brand-border p-6 text-center text-sm text-content-gray">
          Nenhum gateway cadastrado. Adicione a URL de um Gateway que fale o protocolo Anthropic Messages.
        </p>
      )}

      {c.gateways.map((g) => (
        <GatewayCard
          key={g.id}
          gateway={g}
          readOnly={c.readOnly}
          probes={c.probes}
          remoteModels={c.remoteModels[g.id]}
          onEditGateway={c.openEditGateway}
          onRemoveGateway={c.removeGateway}
          onAddModel={c.openNewModel}
          onEditModel={c.openEditModel}
          onRemoveModel={c.removeModel}
          onProbe={c.probe}
          onLoadRemote={c.loadRemote}
        />
      ))}

      {/* Formulário de gateway */}
      {c.gatewayDraft && (
        <GatewayForm
          draft={c.gatewayDraft}
          errors={c.gatewayErrors}
          saving={c.saving}
          keyRequired={c.keyRequired}
          originMoved={c.originMoved}
          onPatch={c.patchGateway}
          onSubmit={c.saveGateway}
          onCancel={() => c.setGatewayDraft(null)}
        />
      )}

      {/* Formulário de modelo */}
      {c.modelDraft && (
        <ModelForm
          draft={c.modelDraft}
          errors={c.modelErrors}
          saving={c.saving}
          remoteModels={c.remoteModels}
          onPatch={c.patchModel}
          onSubmit={c.saveModel}
          onCancel={() => c.setModelDraft(null)}
        />
      )}
    </div>
  )
}
