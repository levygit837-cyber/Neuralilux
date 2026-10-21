'use client'

import { useEffect, useState } from 'react'
import { Cpu, Network } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { gatewayService } from '@/services/gatewayService'
import { useSettingsStore } from '@/stores/useSettingsStore'
import type { AgentType, GatewayAssignment } from '@/types/gateway'

const AGENT_TITLES: Record<AgentType, string> = {
  default: 'Padrão',
  whatsapp_agent: 'Agente do WhatsApp',
}
const AGENT_TYPES = Object.keys(AGENT_TITLES) as AgentType[]

export function InferenceProviderCard() {
  const setActiveTab = useSettingsStore((state) => state.setActiveTab)
  const [assignments, setAssignments] = useState<GatewayAssignment[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    gatewayService
      .assignments()
      .then((data) => {
        if (!cancelled) setAssignments(data)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Falha ao carregar atribuições')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="rounded-2xl border border-border-color bg-card p-7">
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-purple-500/10">
          <Cpu className="h-5 w-5 text-purple-500" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-light">Provedor de Inferência</h3>
          <p className="text-sm text-text-gray">O provedor é o Gateway atribuído a cada agente</p>
        </div>
      </div>

      {error && (
        <p role="alert" className="mb-4 text-sm text-red-400">
          {error}
        </p>
      )}

      <ul className="mb-6 space-y-3">
        {AGENT_TYPES.map((agentType) => {
          const assignment = assignments.find((a) => a.agent_type === agentType)
          return (
            <li
              key={agentType}
              className="flex items-center justify-between rounded-xl border border-border-color bg-input px-4 py-3"
            >
              <span className="text-sm font-medium text-text-light">{AGENT_TITLES[agentType]}</span>
              <span className="text-sm text-text-gray">
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

      <div className="flex justify-end">
        <Button type="button" onClick={() => setActiveTab('gateways')}>
          <Network className="mr-2 h-4 w-4" />
          Gerenciar na aba Gateways
        </Button>
      </div>
    </div>
  )
}
