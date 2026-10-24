import { ShareNetwork } from '@phosphor-icons/react'
import { gatewayService } from '@/services/gatewayService'
import { AGENT_LABELS, AGENT_TYPES, type GatewayAssignment } from '@/types/gateway'
import { selectClass } from './constants'

interface AssignmentsSectionProps {
  assignments: GatewayAssignment[]
  activeModels: { id: string; name: string; gatewayName: string }[]
  disabled: boolean
  run: (action: () => Promise<unknown>) => Promise<boolean>
}

export function AssignmentsSection({ assignments, activeModels, disabled, run }: AssignmentsSectionProps) {
  return (
    <section className="rounded-2xl border border-brand-border bg-brand-card p-7" aria-labelledby="gw-assign">
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
          <ShareNetwork className="h-5 w-5 text-primary-light" aria-hidden="true" />
        </div>
        <div>
          <h3 id="gw-assign" className="text-lg font-semibold text-content-light">Modelo de cada agente</h3>
          <p className="text-sm text-content-gray">
            Cada agente usa o modelo de um Gateway. O tipo Padrão vale para o agente que não tem modelo próprio.
          </p>
        </div>
      </div>
      <div className="space-y-4">
        {AGENT_TYPES.map((agent) => (
          <div key={agent} className="grid items-center gap-3 md:grid-cols-[1fr_1.4fr]">
            <label htmlFor={`assign-${agent}`}>
              <span className="block text-sm font-medium text-content-light">{AGENT_LABELS[agent].title}</span>
              <span className="block text-xs text-content-gray">{AGENT_LABELS[agent].hint}</span>
            </label>
            <select
              id={`assign-${agent}`}
              className={selectClass}
              disabled={disabled}
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
  )
}
