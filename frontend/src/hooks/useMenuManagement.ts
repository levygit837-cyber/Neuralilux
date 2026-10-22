'use client'

import type { FormEvent } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { normalizeCustomAttributes } from '@/components/estoque/helpers'
import type { CategoryFormState, ItemFormState } from '@/components/estoque/types'
import { menuService } from '@/services/menuService'
import { useAuthStore } from '@/stores/useAuthStore'
import type { MenuCategory, MenuItem, MenuManagementPayload } from '@/types/menu'

export function useMenuManagement() {
  const token = useAuthStore((state) => state.token)
  const hasHydrated = useAuthStore((state) => state.hasHydrated)

  const [fetchedMenu, setFetchedMenu] = useState<MenuManagementPayload | null>(null)
  // Sem token o cardápio buscado antes não vale mais: deriva no render em vez de limpar no effect.
  const menu = token ? fetchedMenu : null
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Sem token não há fetch: o estado deriva de hasHydrated/token em vez de ser setado no effect.
  const isLoggedOut = hasHydrated && !token
  const displayedError = isLoggedOut ? 'Faça login para acessar o estoque.' : error
  const showSkeleton = isLoading && !isLoggedOut

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

  // Única rota de carga do cardápio, usada pelo effect e pelos handlers de mutação.
  // `isCancelled` evita aplicar resposta de um token/montagem anterior.
  const loadMenu = useCallback(
    (preferredCategoryId?: string | null, isCancelled: () => boolean = () => false): Promise<void> => {
      if (!hasHydrated || !token) {
        return Promise.resolve()
      }

      return menuService
        .getMenu()
        .then((payload) => {
          if (isCancelled()) return
          setFetchedMenu(payload)
          setSelectedCategoryId((current) => {
            const nextSelection = preferredCategoryId ?? current
            if (nextSelection && payload.categories.some((category) => category.id === nextSelection)) {
              return nextSelection
            }
            return payload.categories[0]?.id ?? null
          })
          setError(null)
        })
        .catch((err: unknown) => {
          if (isCancelled()) return
          setError(err instanceof Error ? err.message : 'Não foi possível carregar o estoque.')
        })
        .finally(() => {
          if (!isCancelled()) setIsLoading(false)
        })
    },
    [hasHydrated, token]
  )

  useEffect(() => {
    let cancelled = false
    void loadMenu(null, () => cancelled)

    return () => {
      cancelled = true
    }
  }, [loadMenu])

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
    if (!token || !categoryForm) {
      return
    }

    setIsSaving(true)
    try {
      if (categoryForm.id) {
        await menuService.updateCategory(categoryForm.id, {
          name: categoryForm.name,
          description: categoryForm.description.trim() || null,
        })
      } else {
        const createdCategory = await menuService.createCategory({
          name: categoryForm.name,
          description: categoryForm.description.trim() || null,
        })
        await loadMenu(createdCategory.id)
        setCategoryForm(null)
        return
      }

      await loadMenu(categoryForm.id)
      setCategoryForm(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível salvar a categoria.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleItemSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!token || !itemForm) {
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

    setIsSaving(true)
    try {
      if (itemForm.id) {
        await menuService.updateItem(itemForm.id, payload)
      } else {
        await menuService.createItem(payload)
      }

      await loadMenu(itemForm.category_id)
      setItemForm(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível salvar o item.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteCategory = async (category: MenuCategory) => {
    if (!token) {
      return
    }

    const confirmed = window.confirm(
      `Excluir a categoria "${category.name}" também removerá todos os itens dela. Deseja continuar?`
    )
    if (!confirmed) {
      return
    }

    setIsSaving(true)
    try {
      await menuService.deleteCategory(category.id)
      await loadMenu(category.id === selectedCategoryId ? null : selectedCategoryId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível remover a categoria.')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteItem = async (item: MenuItem) => {
    if (!token) {
      return
    }

    const confirmed = window.confirm(`Excluir o item "${item.name}"?`)
    if (!confirmed) {
      return
    }

    setIsSaving(true)
    try {
      await menuService.deleteItem(item.id)
      await loadMenu(item.category_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível remover o item.')
    } finally {
      setIsSaving(false)
    }
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
