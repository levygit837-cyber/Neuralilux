'use client'

import { ArrowsClockwise } from '@phosphor-icons/react'

import { OrderCard } from '@/components/pedidos/OrderCard'
import { Button } from '@/components/ui/Button'
import { useOrderPanel } from '@/hooks/useOrderPanel'

const FEEDBACK_STYLES = {
  success: 'border-status-success/30 bg-status-success/10 text-status-success',
  warning: 'border-status-warning/30 bg-status-warning/10 text-status-warning',
  error: 'border-status-error/30 bg-status-error/10 text-status-error',
} as const

const FILTERS = [
  { value: 'active', label: 'Ativos' },
  { value: 'done', label: 'Finalizados' },
] as const

export default function PedidosPage() {
  const {
    orders,
    total,
    filter,
    selectFilter,
    hasMore,
    isLoadingMore,
    loadMore,
    showSkeleton,
    displayedError,
    pendingOrderId,
    feedback,
    changeStatus,
    reload,
  } = useOrderPanel()

  return (
    <div className="p-4 sm:p-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-content-muted">
            Acompanhe os pedidos confirmados. A cada mudança de status o cliente recebe um aviso no WhatsApp.
          </p>
          <Button type="button" variant="secondary" size="sm" onClick={() => void reload()}>
            <ArrowsClockwise className="h-4 w-4" aria-hidden="true" />
            Atualizar
          </Button>
        </div>

        <div role="group" aria-label="Filtrar pedidos" className="flex gap-2">
          {FILTERS.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={filter === option.value ? 'primary' : 'secondary'}
              aria-pressed={filter === option.value}
              onClick={() => selectFilter(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>

        <div aria-live="polite">
          {feedback && (
            <div className={`rounded-2xl border px-4 py-3 text-sm ${FEEDBACK_STYLES[feedback.kind]}`}>
              {feedback.text}
            </div>
          )}
        </div>

        {displayedError && (
          <div role="alert" className="rounded-2xl border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-status-error">
            {displayedError}
          </div>
        )}

        {showSkeleton ? (
          <div className="h-64 animate-pulse rounded-3xl bg-brand-card" />
        ) : orders.length === 0 ? (
          <p className="rounded-3xl border border-brand-border bg-brand-card p-8 text-center text-sm text-content-muted">
            {filter === 'active' ? 'Nenhum pedido em andamento.' : 'Nenhum pedido finalizado ainda.'}
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

        {!showSkeleton && orders.length > 0 && (
          <div className="flex flex-col items-center gap-2">
            <p className="text-xs text-content-muted">
              Mostrando {orders.length} de {total}
            </p>
            {hasMore && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={isLoadingMore}
                aria-busy={isLoadingMore}
                onClick={() => void loadMore()}
              >
                Carregar mais
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
