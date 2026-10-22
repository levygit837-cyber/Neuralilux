import { apiRequest, jsonBody } from '@/services/http'
import type { OrderStatusChangeResult, OrderTransition, PanelOrder } from '@/types/order'

const FALLBACK = 'Erro ao carregar os pedidos'

export const orderService = {
  async list(): Promise<PanelOrder[]> {
    const body = await apiRequest<{ orders: PanelOrder[] }>('/orders', { method: 'GET' }, FALLBACK)
    return body.orders
  },

  changeStatus(orderId: string, status: OrderTransition): Promise<OrderStatusChangeResult> {
    return apiRequest<OrderStatusChangeResult>(
      `/orders/${orderId}/status`,
      jsonBody('POST', { status }),
      'Erro ao mudar o status do pedido'
    )
  },
}
