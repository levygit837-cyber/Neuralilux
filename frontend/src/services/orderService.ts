import { apiRequest, jsonBody } from '@/services/http'
import type { OrderListFilter, OrderPage, OrderStatusChangeResult, OrderTransition } from '@/types/order'

const FALLBACK = 'Erro ao carregar os pedidos'

export const orderService = {
  list(status: OrderListFilter, offset: number, limit: number): Promise<OrderPage> {
    const query = new URLSearchParams({ status, offset: String(offset), limit: String(limit) })
    return apiRequest<OrderPage>(`/orders?${query}`, { method: 'GET' }, FALLBACK)
  },

  changeStatus(orderId: string, status: OrderTransition): Promise<OrderStatusChangeResult> {
    return apiRequest<OrderStatusChangeResult>(
      `/orders/${orderId}/status`,
      jsonBody('POST', { status }),
      'Erro ao mudar o status do pedido'
    )
  },
}
