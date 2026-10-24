'use client'

import { useQuery } from '@tanstack/react-query'
import { Cpu, Network } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useCurrentUser } from '@/hooks/useCurrentUser'
import { useSessionReady } from '@/hooks/useSessionReady'
import { queryKeys } from '@/lib/queryKeys'
import { gatewayService } from '@/services/gatewayService'
import { useSettingsStore } from '@/stores/useSettingsStore'
import { AGENT_LABELS, AGENT_TYPES } from '@/types/gateway'

export function InferenceProviderCard() {
  const setActiveTab = useSettingsStore((state) => state.setActiveTab)
  // Leitura enxuta, liberada a qualquer usuário logado: a lista completa de Gateways (com URL) é só de superusuário.
  const query = useQuery({
    queryKey: queryKeys.gatewayActiveModels,
    queryFn: gatewayService.activeModels,
    enabled: useSessionReady(),
  })
  const canManage = useCurrentUser().data?.is_superuser !== false
  const assignments = query.data ?? []
  const loading = query.isPending
  const error = query.isError ? (query.error instanceof Error ? query.error.message : 'Falha ao carregar atribuições') : null

  return (
    <div className="rounded-2xl border border-brand-border bg-brand-card p-7">
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
          <Cpu className="h-5 w-5 text-primary-light" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-content-light">Provedor de Inferência</h3>
          <p className="text-sm text-content-gray">O provedor é o Gateway atribuído a cada agente</p>
        </div>
      </div>

      {error && (
        <p role="alert" className="mb-4 text-sm text-status-error">
          {error}
        </p>
      )}

      <ul className="mb-6 space-y-3">
        {AGENT_TYPES.map((agentType) => {
          const assignment = assignments.find((a) => a.agent_type === agentType)
          return (
            <li
              key={agentType}
              className="flex items-center justify-between rounded-xl border border-brand-border bg-brand-base px-4 py-3"
            >
              <span className="text-sm font-medium text-content-light">{AGENT_LABELS[agentType].title}</span>
              <span className="text-sm text-content-gray">
                {loading
                  ? 'Carregando...'
                  : assignment
                    ? `${assignment.gateway_name} · ${assignment.model_name}`
                    : 'Sem gateway atribuído'}
              </span>
            </li>
          )
        })}
      </ul>

      {canManage && (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setActiveTab('gateways')}>
            <Network className="mr-2 h-4 w-4" />
            Gerenciar na aba Gateways
          </Button>
        </div>
      )}
    </div>
  )
}
