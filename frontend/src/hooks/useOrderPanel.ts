'use client'

import { useCallback, useEffect, useState } from 'react'

import { orderService } from '@/services/orderService'
import { useAuthStore } from '@/stores/useAuthStore'
import type { OrderTransition, PanelOrder } from '@/types/order'

export interface OrderFeedback {
  kind: 'success' | 'warning' | 'error'
  text: string
}

export function useOrderPanel() {
  const token = useAuthStore((state) => state.token)
  const hasHydrated = useAuthStore((state) => state.hasHydrated)

  const [orders, setOrders] = useState<PanelOrder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pendingOrderId, setPendingOrderId] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<OrderFeedback | null>(null)
  const isLoggedOut = hasHydrated && !token
  const displayedError = isLoggedOut ? 'Faça login para acessar os pedidos.' : error

  const load = useCallback(
    (isCancelled: () => boolean = () => false): Promise<void> => {
      if (!hasHydrated || !token) return Promise.resolve()
      return orderService
        .list()
        .then((list) => {
          if (isCancelled()) return
          setOrders(list)
          setError(null)
        })
        .catch((err: unknown) => {
          if (isCancelled()) return
          setError(err instanceof Error ? err.message : 'Não foi possível carregar os pedidos.')
        })
        .finally(() => {
          if (!isCancelled()) setIsLoading(false)
        })
    },
    [hasHydrated, token]
  )

  useEffect(() => {
    let cancelled = false
    void load(() => cancelled)
    return () => {
      cancelled = true
    }
  }, [load])

  const changeStatus = async (order: PanelOrder, target: OrderTransition) => {
    setPendingOrderId(order.id)
    setFeedback(null)
    try {
      const result = await orderService.changeStatus(order.id, target)
      setOrders((current) => current.map((row) => (row.id === order.id ? result.order : row)))
      setFeedback(
        result.notification.sent
          ? { kind: 'success', text: `Pedido ${order.order_number} atualizado e cliente avisado no WhatsApp.` }
          : {
              kind: 'warning',
              text: `Pedido ${order.order_number} atualizado, mas o cliente não foi avisado: ${result.notification.error ?? 'falha no envio'}`,
            }
      )
    } catch (err) {
      setFeedback({ kind: 'error', text: err instanceof Error ? err.message : 'Não foi possível mudar o status.' })
      await load()
    } finally {
      setPendingOrderId(null)
    }
  }

  return {
    orders,
    showSkeleton: isLoading && !isLoggedOut,
    displayedError,
    pendingOrderId,
    feedback,
    changeStatus,
    reload: () => load(),
  }
}
