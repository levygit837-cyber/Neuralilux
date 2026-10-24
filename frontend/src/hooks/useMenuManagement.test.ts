// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useMenuManagement } from '@/hooks/useMenuManagement'
import { HttpError } from '@/services/http'
import { menuService } from '@/services/menuService'
import { useAuthStore } from '@/stores/useAuthStore'
import { queryWrapper } from '@/test/queryWrapper'
import type { MenuItem, MenuManagementPayload } from '@/types/menu'

vi.mock('@/services/menuService', () => ({
  menuService: {
    getMenu: vi.fn(),
    createCategory: vi.fn(),
    updateCategory: vi.fn(),
    deleteCategory: vi.fn(),
    createItem: vi.fn(),
    updateItem: vi.fn(),
    deleteItem: vi.fn(),
  },
}))

const item = { id: 'i1', category_id: 'c1', name: 'Pizza' } as MenuItem
const menu = (items: MenuItem[]) =>
  ({ catalog: null, categories: [{ id: 'c1', name: 'Pizzas' }], items }) as unknown as MenuManagementPayload

describe('useMenuManagement', () => {
  beforeEach(() => {
    useAuthStore.setState({ token: 'token', hasHydrated: true })
    vi.stubGlobal('confirm', vi.fn().mockReturnValue(true))
    window.confirm = vi.fn().mockReturnValue(true)
  })

  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
    vi.unstubAllGlobals()
    useAuthStore.setState({ token: null, hasHydrated: false })
  })

  it('apagar um item refaz o cardápio e o item some da tela', async () => {
    vi.mocked(menuService.getMenu).mockResolvedValueOnce(menu([item])).mockResolvedValue(menu([]))
    vi.mocked(menuService.deleteItem).mockResolvedValue(undefined)

    const { result } = renderHook(() => useMenuManagement(), { wrapper: queryWrapper().Wrapper })
    await waitFor(() => expect(result.current.categoryItems).toHaveLength(1))

    await act(async () => {
      await result.current.handleDeleteItem(item)
    })

    await waitFor(() => expect(result.current.categoryItems).toHaveLength(0))
    expect(menuService.getMenu).toHaveBeenCalledTimes(2)
  })

  it('o erro ao apagar aparece na tela', async () => {
    vi.mocked(menuService.getMenu).mockResolvedValue(menu([item]))
    vi.mocked(menuService.deleteItem).mockRejectedValue(new HttpError(500, 'Item em uso'))

    const { result } = renderHook(() => useMenuManagement(), { wrapper: queryWrapper().Wrapper })
    await waitFor(() => expect(result.current.categoryItems).toHaveLength(1))

    await act(async () => {
      await result.current.handleDeleteItem(item)
    })

    await waitFor(() => expect(result.current.displayedError).toBe('Item em uso'))
  })

  it('a falha ao carregar o cardápio fica visível', async () => {
    vi.mocked(menuService.getMenu).mockRejectedValue(new HttpError(500, 'Erro ao carregar estoque'))

    const { result } = renderHook(() => useMenuManagement(), { wrapper: queryWrapper().Wrapper })

    await waitFor(() => expect(result.current.displayedError).toBe('Erro ao carregar estoque'))
    expect(result.current.showSkeleton).toBe(false)
  })
})
