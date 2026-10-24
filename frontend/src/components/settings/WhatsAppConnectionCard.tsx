'use client'

import Link from 'next/link'
import { Smartphone, Wifi, WifiOff, Loader2 } from 'lucide-react'
import { ROUTES } from '@/lib/constants'
import { useInstances } from '@/hooks/useInstances'
import type { InstanceStatus } from '@/services/instanceService'

const STATUS_CONFIG: Record<InstanceStatus, { label: string; color: string; bgColor: string; icon: typeof Wifi }> = {
  connected: { label: 'Conectado', color: 'text-status-success', bgColor: 'bg-status-success/10', icon: Wifi },
  disconnected: { label: 'Desconectado', color: 'text-status-error', bgColor: 'bg-status-error/10', icon: WifiOff },
  connecting: { label: 'Conectando', color: 'text-status-warning', bgColor: 'bg-status-warning/10', icon: Loader2 },
}

const LINK_CLASS =
  'inline-flex items-center justify-center rounded-md border border-brand-border px-4 py-2 text-sm font-semibold text-content-gray transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'

export function WhatsAppConnectionCard() {
  const query = useInstances()
  const instances = query.data ?? null
  const error = query.isError ? (query.error instanceof Error ? query.error.message : 'Falha ao listar as instâncias') : null

  return (
    <div className="rounded-2xl border border-brand-border bg-brand-card p-7">
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-status-success/10">
          <Smartphone className="h-5 w-5 text-status-success" />
        </div>
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-content-light">Conexão WhatsApp</h3>
          <p className="text-sm text-content-gray">Status das suas Instances; a conexão é gerenciada em Instâncias</p>
        </div>
      </div>

      {error && (
        <p role="alert" className="mb-4 rounded-lg bg-status-error/10 p-3 text-sm text-status-error">
          {error}
        </p>
      )}

      {instances === null && !error && <p role="status" className="text-sm text-content-gray">Carregando instâncias...</p>}

      {instances?.length === 0 && (
        <p className="text-sm text-content-gray">Você ainda não tem nenhuma Instance. Crie a primeira em Instâncias.</p>
      )}

      {instances && instances.length > 0 && (
        <ul className="space-y-3">
          {instances.map((instance) => {
            const status = STATUS_CONFIG[instance.status]
            const StatusIcon = status.icon
            return (
              <li
                key={instance.id}
                className="flex items-center justify-between rounded-xl border border-brand-border px-4 py-3"
              >
                <span className="text-sm font-medium text-content-light">{instance.name}</span>
                <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${status.bgColor} ${status.color}`}>
                  <StatusIcon className={`h-3.5 w-3.5 ${instance.status === 'connecting' ? 'animate-spin' : ''}`} />
                  {status.label}
                </span>
              </li>
            )
          })}
        </ul>
      )}

      <div className="mt-6 flex justify-end">
        <Link href={ROUTES.INSTANCES} className={LINK_CLASS}>
          Gerenciar Instances
        </Link>
      </div>
    </div>
  )
}
