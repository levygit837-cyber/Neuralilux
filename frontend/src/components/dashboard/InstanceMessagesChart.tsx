'use client'

import { DeviceMobile } from '@phosphor-icons/react'
import { Card } from '@/components/ui/Card'
import { WidgetError } from '@/components/dashboard/WidgetError'
import { formatCompactNumber } from '@/lib/utils'
import type { InstanceMessages } from '@/types/dashboard'

interface InstanceMessagesChartProps {
  /** `undefined` enquanto carrega. */
  instances?: InstanceMessages[]
  error?: string | null
  onRetry: () => void
}

/** Messages do período por Instance, com o nome real de cada uma. */
export function InstanceMessagesChart({ instances, error, onRetry }: InstanceMessagesChartProps) {
  const maxCount = Math.max(...(instances ?? []).map((i) => i.count), 1)

  return (
    <Card className="flex h-[380px] animate-slide-up flex-col delay-400">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h3 className="font-medium text-content-light">Mensagens por Instance</h3>
          <p className="mt-1 text-xs text-content-muted">Messages do período em cada número conectado</p>
        </div>
        <div className="rounded bg-brand-base/50 p-2 text-primary-light">
          <DeviceMobile weight="regular" className="text-xl" aria-hidden="true" />
        </div>
      </div>

      {error ? (
        <div className="flex flex-1 flex-col">
          <WidgetError message={error} onRetry={onRetry} />
        </div>
      ) : !instances ? (
        <div className="flex flex-1 items-center justify-center" aria-busy="true">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : instances.length === 0 ? (
        <p className="flex flex-1 items-center justify-center text-xs text-content-muted">Nenhuma Instance ainda</p>
      ) : (
        <ul className="flex-1 space-y-4 overflow-y-auto pr-1">
          {instances.map((instance) => (
            <li key={instance.instance_id}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="truncate font-medium text-content-light">{instance.name}</span>
                <span className="text-content-muted">{formatCompactNumber(instance.count)}</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-brand-base">
                <div
                  className="h-full rounded-full bg-primary transition-all duration-700"
                  style={{ width: `${instance.count > 0 ? Math.max((instance.count / maxCount) * 100, 2) : 0}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
