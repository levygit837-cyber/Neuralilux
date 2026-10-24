'use client'

import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { useSessionReady } from '@/hooks/useSessionReady'
import { queryKeys } from '@/lib/queryKeys'
import { orderService } from '@/services/orderService'
import { useAuthStore } from '@/stores/useAuthStore'
import type { OrderListFilter, OrderTransition, PanelOrder } from '@/types/order'

export const ORDER_PAGE_SIZE = 20

export interface OrderFeedback {
  kind: 'success' | 'warning' | 'error'
  text: string
}

const messageOf = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback)

export function useOrderPanel() {
  const queryClient = useQueryClient()
  const enabled = useSessionReady()
  const isLoggedOut = useAuthStore((state) => state.hasHydrated && !state.isAuthenticated)

  const [filter, setFilter] = useState<OrderListFilter>('active')
  const [feedback, setFeedback] = useState<OrderFeedback | null>(null)

  // O servidor ordena por data: o que já está na tela é o começo da lista, então o próximo trecho começa após ele.
  const query = useInfiniteQuery({
    queryKey: queryKeys.ordersByFilter(filter),
    queryFn: ({ pageParam }) => orderService.list(filter, pageParam, ORDER_PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((sum, page) => sum + page.orders.length, 0)
      return loaded < last.total ? loaded : undefined
    },
    enabled,
  })

  const orders = useMemo(() => {
    const seen = new Set<string>()
    const rows: PanelOrder[] = []
    for (const page of query.data?.pages ?? []) {
      for (const row of page.orders) {
        if (!seen.has(row.id)) {
          seen.add(row.id)
          rows.push(row)
        }
      }
    }
    return rows
  }, [query.data])
  const total = query.data?.pages[query.data.pages.length - 1]?.total ?? 0

  const mutation = useMutation({
    mutationFn: ({ order, target }: { order: PanelOrder; target: OrderTransition }) =>
      orderService.changeStatus(order.id, target),
    onSuccess: (result, { order }) => {
      setFeedback(
        result.notification.sent
          ? { kind: 'success', text: `Pedido ${order.order_number} atualizado e cliente avisado no WhatsApp.` }
          : {
              kind: 'warning',
              text: `Pedido ${order.order_number} atualizado, mas o cliente não foi avisado: ${result.notification.error ?? 'falha no envio'}`,
            }
      )
    },
    onError: (err) => setFeedback({ kind: 'error', text: messageOf(err, 'Não foi possível mudar o status.') }),
    // Sucesso ou falha, as duas listas (ativos e finalizados) podem ter mudado.
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.orders }),
  })

  const selectFilter = (next: OrderListFilter) => {
    if (next === filter) return
    setFeedback(null)
    setFilter(next)
  }

  const queryError = query.isError ? messageOf(query.error, 'Não foi possível carregar os pedidos.') : null

  return {
    orders,
    total,
    filter,
    selectFilter,
    hasMore: query.hasNextPage,
    isLoadingMore: query.isFetchingNextPage,
    loadMore: () => query.fetchNextPage(),
    showSkeleton: query.isPending && !isLoggedOut && enabled,
    displayedError: isLoggedOut ? 'Faça login para acessar os pedidos.' : queryError,
    pendingOrderId: mutation.isPending ? mutation.variables.order.id : null,
    feedback,
    changeStatus: (order: PanelOrder, target: OrderTransition) => {
      setFeedback(null)
      return mutation.mutateAsync({ order, target }).catch(() => undefined)
    },
    reload: () => query.refetch(),
  }
}
