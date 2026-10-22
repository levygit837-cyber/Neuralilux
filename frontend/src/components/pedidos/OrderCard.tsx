import { Button } from '@/components/ui/Button'
import type { OrderTransition, PanelOrder, RefundStatus } from '@/types/order'

const ACTION_LABELS: Record<OrderTransition, string> = {
  in_production: 'Em preparo',
  sent: 'Saiu para entrega',
  delivered: 'Entregue',
  cancelled: 'Cancelar pedido',
}

const REFUND_LABELS: Record<RefundStatus, string> = {
  pending: 'Estornar Pix (pago)',
  verify: 'Conferir Pix no banco',
  refunded: 'Pix estornado',
  dismissed: 'Pix conferido, sem estorno',
}

const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })

export function OrderCard({
  order,
  isBusy,
  onChangeStatus,
}: {
  order: PanelOrder
  isBusy: boolean
  onChangeStatus: (order: PanelOrder, target: OrderTransition) => void
}) {
  return (
    <article
      aria-label={`Pedido ${order.order_number}`}
      className="rounded-3xl border border-border-color bg-card p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-text-light">Pedido {order.order_number}</h3>
          <p className="text-sm text-text-muted">
            {order.customer_name ?? 'Cliente sem nome'}
            {order.customer_phone ? ` · ${order.customer_phone}` : ''}
          </p>
        </div>
        <span
          className={
            order.being_altered
              ? 'rounded-full bg-warning/10 px-3 py-1 text-xs font-medium text-warning'
              : order.status === 'cancelled'
                ? 'rounded-full bg-error/10 px-3 py-1 text-xs font-medium text-error'
                : 'rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary-light'
          }
        >
          {order.status_label}
        </span>
      </div>

      <ul className="mt-4 space-y-1 text-sm text-text-gray">
        {order.items.map((line, index) => (
          <li key={`${line.name}-${index}`} className="flex justify-between gap-3">
            <span>
              {line.quantity}× {line.name}
            </span>
            <span>{currency.format(line.subtotal)}</span>
          </li>
        ))}
      </ul>

      <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-border-color pt-4 text-sm">
        <dt className="text-text-muted">Total</dt>
        <dd className="text-right font-semibold text-text-light">{currency.format(order.total_amount)}</dd>
        <dt className="text-text-muted">Pagamento</dt>
        <dd className="text-right text-text-gray">{order.payment_method ?? 'não informado'}</dd>
        <dt className="text-text-muted">Entrega</dt>
        <dd className="text-right text-text-gray">{order.delivery_type ?? 'não informado'}</dd>
      </dl>

      {order.refund_status && (
        <p role="note" className="mt-3 rounded-xl bg-warning/10 px-3 py-2 text-sm text-warning">
          {REFUND_LABELS[order.refund_status]}
        </p>
      )}
      {order.being_altered && (
        <p role="note" className="mt-3 text-sm text-text-muted">
          O cliente está alterando este pedido. Ele volta a andar quando for reconfirmado.
        </p>
      )}

      {order.allowed_transitions.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {order.allowed_transitions.map((target) => (
            <Button
              key={target}
              type="button"
              size="sm"
              variant={target === 'cancelled' ? 'secondary' : 'primary'}
              disabled={isBusy}
              onClick={() => onChangeStatus(order, target)}
              aria-label={`${ACTION_LABELS[target]} (pedido ${order.order_number})`}
            >
              {ACTION_LABELS[target]}
            </Button>
          ))}
        </div>
      )}
    </article>
  )
}
