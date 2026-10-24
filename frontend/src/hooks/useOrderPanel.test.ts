// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useOrderPanel } from '@/hooks/useOrderPanel'
import { HttpError } from '@/services/http'
import { orderService } from '@/services/orderService'
import { useAuthStore } from '@/stores/useAuthStore'
import { queryWrapper } from '@/test/queryWrapper'
import type { OrderStatus, PanelOrder } from '@/types/order'

vi.mock('@/services/orderService', () => ({ orderService: { list: vi.fn(), changeStatus: vi.fn() } }))

const order = (status: OrderStatus): PanelOrder =>
  ({ id: 'o1', order_number: '#1', status, status_label: status, allowed_transitions: ['sent'] }) as PanelOrder

describe('useOrderPanel', () => {
  beforeEach(() => {
    useAuthStore.setState({ isAuthenticated: true, hasHydrated: true })
  })

  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
    useAuthStore.setState({ isAuthenticated: false, hasHydrated: false })
  })

  it('mudar o status refaz a lista e mostra o pedido atualizado', async () => {
    vi.mocked(orderService.list)
      .mockResolvedValueOnce({ orders: [order('in_production')], total: 1 })
      .mockResolvedValue({ orders: [order('sent')], total: 1 })
    vi.mocked(orderService.changeStatus).mockResolvedValue({
      order: order('sent'),
      notification: { sent: true, error: null },
    })

    const { result } = renderHook(() => useOrderPanel(), { wrapper: queryWrapper().Wrapper })
    await waitFor(() => expect(result.current.orders[0]?.status).toBe('in_production'))

    await act(async () => {
      await result.current.changeStatus(order('in_production'), 'sent')
    })

    await waitFor(() => expect(result.current.orders[0]?.status).toBe('sent'))
    expect(orderService.list).toHaveBeenCalledTimes(2)
    expect(result.current.feedback?.kind).toBe('success')
  })

  it('o erro ao mudar o status aparece no feedback e a lista é refeita', async () => {
    vi.mocked(orderService.list).mockResolvedValue({ orders: [order('in_production')], total: 1 })
    vi.mocked(orderService.changeStatus).mockRejectedValue(new HttpError(409, 'Pedido em alteração'))

    const { result } = renderHook(() => useOrderPanel(), { wrapper: queryWrapper().Wrapper })
    await waitFor(() => expect(result.current.orders).toHaveLength(1))

    await act(async () => {
      await result.current.changeStatus(order('in_production'), 'sent')
    })

    expect(result.current.feedback).toEqual({ kind: 'error', text: 'Pedido em alteração' })
    await waitFor(() => expect(orderService.list).toHaveBeenCalledTimes(2))
  })

  it('a falha ao carregar a lista fica visível', async () => {
    vi.mocked(orderService.list).mockRejectedValue(new HttpError(500, 'Erro ao carregar os pedidos'))

    const { result } = renderHook(() => useOrderPanel(), { wrapper: queryWrapper().Wrapper })

    await waitFor(() => expect(result.current.displayedError).toBe('Erro ao carregar os pedidos'))
    expect(result.current.showSkeleton).toBe(false)
  })
})
