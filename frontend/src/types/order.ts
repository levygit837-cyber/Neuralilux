export type OrderStatus =
  | 'open'
  | 'collecting_data'
  | 'ready_for_confirmation'
  | 'closed'
  | 'in_production'
  | 'sent'
  | 'delivered'
  | 'cancelled'
  | 'abandoned'

/** Status para os quais a Company pode mover um Order pelo painel. */
export type OrderTransition = 'in_production' | 'sent' | 'delivered' | 'cancelled'

export type RefundStatus = 'pending' | 'verify' | 'refunded' | 'dismissed'

export interface OrderLine {
  name: string
  quantity: number
  subtotal: number
}

export interface PanelOrder {
  id: string
  order_number: string
  status: OrderStatus
  status_label: string
  being_altered: boolean
  allowed_transitions: OrderTransition[]
  customer_name: string | null
  customer_phone: string | null
  items: OrderLine[]
  total_amount: number
  payment_method: string | null
  delivery_type: string | null
  refund_status: RefundStatus | null
  opened_at: string | null
}

export interface OrderNotification {
  sent: boolean
  error: string | null
}

export interface OrderStatusChangeResult {
  order: PanelOrder
  notification: OrderNotification
}

/** `active`: recebido, em preparo, saiu e em alteração. `done`: entregue e cancelado. */
export type OrderListFilter = 'active' | 'done'

export interface OrderPage {
  orders: PanelOrder[]
  total: number
}
