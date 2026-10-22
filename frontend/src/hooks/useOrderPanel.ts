'use client'

import { useCallback, useEffect, useState } from 'react'

import { orderService } from '@/services/orderService'
import { useAuthStore } from '@/stores/useAuthStore'
import type { OrderListFilter, OrderTransition, PanelOrder } from '@/types/order'

export const ORDER_PAGE_SIZE = 20

export interface OrderFeedback {
  kind: 'success' | 'warning' | 'error'
  text: string
}

/** Status que tiram o Order da lista de ativos. */
const FINISHED = ['delivered', 'cancelled']

export function useOrderPanel() {
  const token = useAuthStore((state) => state.token)
  const hasHydrated = useAuthStore((state) => state.hasHydrated)

  const [filter, setFilter] = useState<OrderListFilter>('active')
  const [orders, setOrders] = useState<PanelOrder[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingOrderId, setPendingOrderId] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<OrderFeedback | null>(null)
  const isLoggedOut = hasHydrated && !token
  const displayedError = isLoggedOut ? 'Faça login para acessar os pedidos.' : error

  const load = useCallback(
    (isCancelled: () => boolean = () => false): Promise<void> => {
      if (!hasHydrated || !token) return Promise.resolve()
      return orderService
        .list(filter, 0, ORDER_PAGE_SIZE)
        .then((page) => {
          if (isCancelled()) return
          setOrders(page.orders)
          setTotal(page.total)
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
    [hasHydrated, token, filter]
  )

  useEffect(() => {
    let cancelled = false
    void load(() => cancelled)
    return () => {
      cancelled = true
    }
  }, [load])

  const selectFilter = (next: OrderListFilter) => {
    if (next === filter) return
    setOrders([])
    setTotal(0)
    setIsLoading(true)
    setFeedback(null)
    setFilter(next)
  }

  const loadMore = async () => {
    setIsLoadingMore(true)
    try {
      // O servidor ordena por data: o que já está na tela é o começo da lista, então o próximo trecho começa após ele.
      const page = await orderService.list(filter, orders.length, ORDER_PAGE_SIZE)
      setOrders((current) => {
        const known = new Set(current.map((row) => row.id))
        return [...current, ...page.orders.filter((row) => !known.has(row.id))]
      })
      setTotal(page.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível carregar mais pedidos.')
    } finally {
      setIsLoadingMore(false)
    }
  }

  const changeStatus = async (order: PanelOrder, target: OrderTransition) => {
    setPendingOrderId(order.id)
    setFeedback(null)
    try {
      const result = await orderService.changeStatus(order.id, target)
      if (filter === 'active' && FINISHED.includes(result.order.status)) {
        // Saiu da lista de ativos; o servidor também a encurtou, então o próximo `loadMore` continua certo.
        setOrders((current) => current.filter((row) => row.id !== order.id))
        setTotal((current) => Math.max(0, current - 1))
      } else {
        setOrders((current) => current.map((row) => (row.id === order.id ? result.order : row)))
      }
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
    total,
    filter,
    selectFilter,
    hasMore: orders.length < total,
    isLoadingMore,
    loadMore,
    showSkeleton: isLoading && !isLoggedOut,
    displayedError,
    pendingOrderId,
    feedback,
    changeStatus,
    reload: () => load(),
  }
}
