'use client'

import { ArrowsClockwise } from '@phosphor-icons/react'

import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { OrderCard } from '@/components/pedidos/OrderCard'
import { Button } from '@/components/ui/Button'
import { useOrderPanel } from '@/hooks/useOrderPanel'

const FEEDBACK_STYLES = {
  success: 'border-success/30 bg-success/10 text-success',
  warning: 'border-warning/30 bg-warning/10 text-warning',
  error: 'border-error/30 bg-error/10 text-error',
} as const

export default function PedidosPage() {
  const { orders, showSkeleton, displayedError, pendingOrderId, feedback, changeStatus, reload } = useOrderPanel()

  return (
    <div className="flex h-screen overflow-hidden bg-dark">
      <Sidebar />

      <div className="flex min-h-0 flex-1 flex-col">
        <Header title="Pedidos" />

        <main className="min-h-0 flex-1 overflow-auto p-8">
          <div className="mx-auto flex max-w-5xl flex-col gap-6">
            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-text-muted">
                Acompanhe os pedidos confirmados. A cada mudança de status o cliente recebe um aviso no WhatsApp.
              </p>
              <Button type="button" variant="secondary" size="sm" onClick={() => void reload()}>
                <ArrowsClockwise className="h-4 w-4" aria-hidden="true" />
                Atualizar
              </Button>
            </div>

            <div aria-live="polite">
              {feedback && (
                <div className={`rounded-2xl border px-4 py-3 text-sm ${FEEDBACK_STYLES[feedback.kind]}`}>
                  {feedback.text}
                </div>
              )}
            </div>

            {displayedError && (
              <div role="alert" className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                {displayedError}
              </div>
            )}

            {showSkeleton ? (
              <div className="h-64 animate-pulse rounded-3xl bg-card" />
            ) : orders.length === 0 ? (
              <p className="rounded-3xl border border-border-color bg-card p-8 text-center text-sm text-text-muted">
                Nenhum pedido confirmado ainda.
              </p>
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {orders.map((order) => (
                  <OrderCard
                    key={order.id}
                    order={order}
                    isBusy={pendingOrderId === order.id}
                    onChangeStatus={(row, target) => void changeStatus(row, target)}
                  />
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
