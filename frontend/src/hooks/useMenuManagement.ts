'use client'

import type { FormEvent } from 'react'
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { normalizeCustomAttributes } from '@/components/estoque/helpers'
import type { CategoryFormState, ItemFormState } from '@/components/estoque/types'
import { useSessionReady } from '@/hooks/useSessionReady'
import { queryKeys } from '@/lib/queryKeys'
import { menuService } from '@/services/menuService'
import { useAuthStore } from '@/stores/useAuthStore'
import type { MenuCategory, MenuItem } from '@/types/menu'

const messageOf = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback)

export function useMenuManagement() {
  const queryClient = useQueryClient()
  const enabled = useSessionReady()
  const isLoggedOut = useAuthStore((state) => state.hasHydrated && !state.isAuthenticated)

  const query = useQuery({ queryKey: queryKeys.menu, queryFn: menuService.getMenu, enabled })
  const menu = query.data ?? null
  // Categoria escolhida pelo usuário; se sumiu do cardápio (apagada), vale a primeira.
  const [preferredCategoryId, setSelectedCategoryId] = useState<string | null>(null)
  const selectedCategoryId =
    menu?.categories.find((category) => category.id === preferredCategoryId)?.id ?? menu?.categories[0]?.id ?? null
  const [mutationError, setMutationError] = useState<string | null>(null)
  const queryError = query.isError ? messageOf(query.error, 'Não foi possível carregar o estoque.') : null
  const displayedError = isLoggedOut ? 'Faça login para acessar o estoque.' : (mutationError ?? queryError)
  const showSkeleton = query.isPending && enabled

  const [categoryForm, setCategoryForm] = useState<CategoryFormState | null>(null)
  const [itemForm, setItemForm] = useState<ItemFormState | null>(null)

  const selectedCategory = useMemo(
    () => menu?.categories.find((category) => category.id === selectedCategoryId) || null,
    [menu?.categories, selectedCategoryId]
  )

  const categoryItems = useMemo(
    () => menu?.items.filter((item) => item.category_id === selectedCategoryId) || [],
    [menu?.items, selectedCategoryId]
  )

  // Toda mutação do cardápio invalida a query e mostra o erro no banner da tela.
  const mutation = useMutation({
    mutationFn: (action: () => Promise<unknown>) => action(),
    onMutate: () => setMutationError(null),
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.menu }),
  })
  const isSaving = mutation.isPending

  /** Roda a mutação; devolve o resultado ou `undefined` após registrar o erro. */
  const mutate = async <T,>(action: () => Promise<T>, fallback: string): Promise<T | undefined> => {
    try {
      return (await mutation.mutateAsync(action)) as T
    } catch (err) {
      setMutationError(messageOf(err, fallback))
      return undefined
    }
  }

  const openNewCategoryModal = () => {
    setCategoryForm({
      id: null,
      name: '',
      description: '',
    })
  }

  const openEditCategoryModal = (category: MenuCategory) => {
    setCategoryForm({
      id: category.id,
      name: category.name,
      description: category.description || '',
    })
  }

  const openNewItemModal = (categoryId: string) => {
    setItemForm({
      id: null,
      category_id: categoryId,
      name: '',
      description: '',
      price: '',
      is_available: true,
      custom_attributes: [],
    })
  }

  const openEditItemModal = (item: MenuItem) => {
    setItemForm({
      id: item.id,
      category_id: item.category_id,
      name: item.name,
      description: item.description || '',
      price: item.price === null || item.price === undefined ? '' : String(item.price),
      is_available: item.is_available,
      custom_attributes: item.custom_attributes || [],
    })
  }

  const handleCategorySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!enabled || !categoryForm) {
      return
    }

    const body = { name: categoryForm.name, description: categoryForm.description.trim() || null }
    const saved = await mutate(
      () => (categoryForm.id ? menuService.updateCategory(categoryForm.id, body) : menuService.createCategory(body)),
      'Não foi possível salvar a categoria.'
    )
    if (!saved) return
    setSelectedCategoryId((saved as MenuCategory).id)
    setCategoryForm(null)
  }

  const handleItemSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!enabled || !itemForm) {
      return
    }

    const payload = {
      category_id: itemForm.category_id,
      name: itemForm.name,
      description: itemForm.description.trim() || null,
      price: itemForm.price.trim() ? itemForm.price.trim() : null,
      is_available: itemForm.is_available,
      custom_attributes: normalizeCustomAttributes(itemForm.custom_attributes),
    }

    const saved = await mutate(
      () => (itemForm.id ? menuService.updateItem(itemForm.id, payload) : menuService.createItem(payload)),
      'Não foi possível salvar o item.'
    )
    if (!saved) return
    setSelectedCategoryId(itemForm.category_id)
    setItemForm(null)
  }

  const handleDeleteCategory = async (category: MenuCategory) => {
    if (!enabled) {
      return
    }

    const confirmed = window.confirm(
      `Excluir a categoria "${category.name}" também removerá todos os itens dela. Deseja continuar?`
    )
    if (!confirmed) {
      return
    }

    await mutate(() => menuService.deleteCategory(category.id), 'Não foi possível remover a categoria.')
  }

  const handleDeleteItem = async (item: MenuItem) => {
    if (!enabled) {
      return
    }

    const confirmed = window.confirm(`Excluir o item "${item.name}"?`)
    if (!confirmed) {
      return
    }

    await mutate(() => menuService.deleteItem(item.id), 'Não foi possível remover o item.')
  }

  return {
    menu,
    selectedCategoryId,
    setSelectedCategoryId,
    selectedCategory,
    categoryItems,
    isSaving,
    displayedError,
    showSkeleton,
    categoryForm,
    setCategoryForm,
    itemForm,
    setItemForm,
    openNewCategoryModal,
    openEditCategoryModal,
    openNewItemModal,
    openEditItemModal,
    handleCategorySubmit,
    handleItemSubmit,
    handleDeleteCategory,
    handleDeleteItem,
  }
}
