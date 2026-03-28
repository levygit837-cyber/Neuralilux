'use client'

import type { FormEvent, ReactNode } from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Boxes,
  CircleDollarSign,
  PackagePlus,
  Pencil,
  Plus,
  Tag,
  Trash2,
  X,
} from 'lucide-react'

import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { menuService } from '@/services/menuService'
import { useAuthStore } from '@/stores/useAuthStore'
import type { MenuAttribute, MenuCategory, MenuItem, MenuManagementPayload } from '@/types/menu'

type CategoryFormState = {
  id: string | null
  name: string
  description: string
}

type ItemFormState = {
  id: string | null
  category_id: string
  name: string
  description: string
  price: string
  is_available: boolean
  custom_attributes: MenuAttribute[]
}

function ModalFrame({
  title,
  description,
  onClose,
  children,
}: {
  title: string
  description: string
  onClose: () => void
  children: ReactNode
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark/80 px-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-3xl border border-border-color bg-card shadow-2xl">
        <div className="flex items-start justify-between border-b border-border-color px-6 py-5">
          <div>
            <h2 className="text-xl font-semibold text-text-light">{title}</h2>
            <p className="mt-1 text-sm text-text-muted">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-hover p-2 text-text-muted transition-colors hover:bg-border-color hover:text-text-light"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[80vh] overflow-y-auto px-6 py-6">{children}</div>
      </div>
    </div>
  )
}

function formatPrice(price: MenuItem['price']): string {
  if (price === null || price === undefined || price === '') {
    return 'Sem preço'
  }

  const numericPrice = Number(price)
  if (Number.isNaN(numericPrice)) {
    return String(price)
  }

  return numericPrice.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
}

function normalizeCustomAttributes(customAttributes: MenuAttribute[]): MenuAttribute[] {
  return customAttributes
    .map((attribute) => ({
      key: attribute.key.trim(),
      value: attribute.value.trim(),
    }))
    .filter((attribute) => attribute.key && attribute.value)
}

export default function EstoquePage() {
  const token = useAuthStore((state) => state.token)
  const hasHydrated = useAuthStore((state) => state.hasHydrated)

  const [menu, setMenu] = useState<MenuManagementPayload | null>(null)
  const [selectedCategoryId, setSelectedCategoryId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

  const loadMenu = useCallback(
    async (preferredCategoryId?: string | null) => {
      if (!hasHydrated) {
        return
      }

      if (!token) {
        setMenu(null)
        setError('Faça login para acessar o estoque.')
        setIsLoading(false)
        return
      }

      try {
        const payload = await menuService.getMenu(token)
        setMenu(payload)
        setSelectedCategoryId((current) => {
          const nextSelection = preferredCategoryId ?? current
          if (nextSelection && payload.categories.some((category) => category.id === nextSelection)) {
            return nextSelection
          }
          return payload.categories[0]?.id ?? null
        })
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Não foi possível carregar o estoque.')
      } finally {
        setIsLoading(false)
      }
    },
    [hasHydrated, token]
  )

  useEffect(() => {
    if (!hasHydrated) {
      return
    }

    setIsLoading(true)
    void loadMenu()
  }, [hasHydrated, loadMenu])

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
        await menuService.updateCategory(token, categoryForm.id, {
          name: categoryForm.name,
          description: categoryForm.description.trim() || null,
        })
      } else {
        const createdCategory = await menuService.createCategory(token, {
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
        await menuService.updateItem(token, itemForm.id, payload)
      } else {
        await menuService.createItem(token, payload)
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
      await menuService.deleteCategory(token, category.id)
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
      await menuService.deleteItem(token, item.id)
      await loadMenu(item.category_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível remover o item.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-dark">
      <Sidebar />

      <div className="flex min-h-0 flex-1 flex-col">
        <Header title="Estoque" />

        <main className="min-h-0 flex-1 overflow-auto p-8">
          <div className="mx-auto flex max-w-7xl flex-col gap-8">
            <section className="rounded-3xl border border-border-color bg-card p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="space-y-2">
                  <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-primary-light">
                    <Boxes className="h-3.5 w-3.5" />
                    Estoque conectado ao cardápio
                  </div>
                  <h2 className="text-3xl font-semibold text-text-light">
                    Organize categorias, itens e variáveis do seu cardápio
                  </h2>
                  <p className="max-w-3xl text-sm leading-6 text-text-muted">
                    Cadastre novas categorias, adicione itens, marque disponibilidade e mantenha
                    atributos livres por produto para deixar o cardápio mais completo.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  {menu?.catalog && (
                    <div className="rounded-2xl border border-border-color bg-dark px-4 py-3 text-sm text-text-gray">
                      <p className="font-medium text-text-light">{menu.catalog.name}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-text-muted">
                        Fonte {menu.catalog.source_type === 'manual' ? 'manual' : 'importada'}
                      </p>
                    </div>
                  )}
                  <Button type="button" onClick={openNewCategoryModal}>
                    <Plus className="h-4 w-4" />
                    Nova categoria
                  </Button>
                </div>
              </div>
            </section>

            {error && (
              <div className="rounded-2xl border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                {error}
              </div>
            )}

            {isLoading ? (
              <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
                <div className="h-[520px] animate-pulse rounded-3xl bg-card" />
                <div className="h-[520px] animate-pulse rounded-3xl bg-card" />
              </div>
            ) : (
              <div className="grid min-h-0 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
                <section className="rounded-3xl border border-border-color bg-card p-5">
                  <div className="mb-4 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-text-light">Categorias</p>
                      <p className="text-xs text-text-muted">
                        {menu?.categories.length || 0} cadastradas
                      </p>
                    </div>
                    <Button type="button" size="sm" onClick={openNewCategoryModal}>
                      <Plus className="h-4 w-4" />
                      Adicionar
                    </Button>
                  </div>

                  <div className="space-y-3">
                    {menu?.categories.length ? (
                      menu.categories.map((category) => {
                        const isSelected = category.id === selectedCategoryId

                        return (
                          <div
                            key={category.id}
                            onClick={() => setSelectedCategoryId(category.id)}
                            className={`w-full cursor-pointer rounded-2xl border p-4 text-left transition-colors ${
                              isSelected
                                ? 'border-primary bg-primary/10'
                                : 'border-border-color bg-dark hover:border-primary/40 hover:bg-hover'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-medium text-text-light">{category.name}</p>
                                <p className="mt-1 text-xs text-text-muted">
                                  {category.items_count} item(ns)
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    openEditCategoryModal(category)
                                  }}
                                  className="rounded-full bg-hover p-2 text-text-muted hover:text-text-light"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={(event) => {
                                    event.stopPropagation()
                                    void handleDeleteCategory(category)
                                  }}
                                  className="rounded-full bg-hover p-2 text-text-muted hover:text-error"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            </div>

                            {category.description && (
                              <p className="mt-3 text-sm leading-6 text-text-gray">
                                {category.description}
                              </p>
                            )}
                          </div>
                        )
                      })
                    ) : (
                      <div className="rounded-2xl border border-dashed border-border-color bg-dark px-4 py-8 text-center">
                        <Tag className="mx-auto h-8 w-8 text-text-muted" />
                        <p className="mt-4 text-sm font-medium text-text-light">
                          Nenhuma categoria criada
                        </p>
                        <p className="mt-2 text-sm text-text-muted">
                          Comece criando a primeira categoria do seu cardápio.
                        </p>
                        <Button type="button" size="sm" className="mt-4" onClick={openNewCategoryModal}>
                          <Plus className="h-4 w-4" />
                          Criar categoria
                        </Button>
                      </div>
                    )}
                  </div>
                </section>

                <section className="rounded-3xl border border-border-color bg-card p-5">
                  {selectedCategory ? (
                    <>
                      <div className="mb-5 flex flex-col gap-4 border-b border-border-color pb-5 lg:flex-row lg:items-center lg:justify-between">
                        <div>
                          <h3 className="text-2xl font-semibold text-text-light">
                            {selectedCategory.name}
                          </h3>
                          <p className="mt-2 max-w-2xl text-sm leading-6 text-text-muted">
                            {selectedCategory.description ||
                              'Use esta categoria para concentrar itens parecidos e manter o cardápio organizado.'}
                          </p>
                        </div>
                        <Button type="button" onClick={() => openNewItemModal(selectedCategory.id)}>
                          <PackagePlus className="h-4 w-4" />
                          Novo item
                        </Button>
                      </div>

                      <div className="grid gap-4 xl:grid-cols-2">
                        {categoryItems.length ? (
                          categoryItems.map((item) => (
                            <article
                              key={item.id}
                              className="rounded-3xl border border-border-color bg-dark p-5"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="space-y-2">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <h4 className="text-lg font-semibold text-text-light">
                                      {item.name}
                                    </h4>
                                    <span
                                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                                        item.is_available
                                          ? 'bg-success/15 text-success'
                                          : 'bg-warning/15 text-warning'
                                      }`}
                                    >
                                      {item.is_available ? 'Disponível' : 'Indisponível'}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-2 text-sm text-text-gray">
                                    <CircleDollarSign className="h-4 w-4 text-primary-light" />
                                    {formatPrice(item.price)}
                                  </div>
                                </div>

                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => openEditItemModal(item)}
                                    className="rounded-full bg-hover p-2 text-text-muted hover:text-text-light"
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => void handleDeleteItem(item)}
                                    className="rounded-full bg-hover p-2 text-text-muted hover:text-error"
                                  >
                                    <Trash2 className="h-4 w-4" />
                                  </button>
                                </div>
                              </div>

                              <p className="mt-4 text-sm leading-6 text-text-gray">
                                {item.description || 'Sem descrição cadastrada.'}
                              </p>

                              <div className="mt-5">
                                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                                  Variáveis extras
                                </p>
                                {item.custom_attributes.length ? (
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {item.custom_attributes.map((attribute, index) => (
                                      <span
                                        key={`${attribute.key}-${index}`}
                                        className="rounded-full border border-border-color bg-card px-3 py-1.5 text-xs text-text-gray"
                                      >
                                        <strong className="text-text-light">{attribute.key}:</strong>{' '}
                                        {attribute.value}
                                      </span>
                                    ))}
                                  </div>
                                ) : (
                                  <p className="mt-3 text-sm text-text-muted">
                                    Este item ainda não tem variáveis extras.
                                  </p>
                                )}
                              </div>
                            </article>
                          ))
                        ) : (
                          <div className="rounded-3xl border border-dashed border-border-color bg-dark px-6 py-12 text-center xl:col-span-2">
                            <PackagePlus className="mx-auto h-9 w-9 text-text-muted" />
                            <p className="mt-4 text-sm font-medium text-text-light">
                              Nenhum item nesta categoria
                            </p>
                            <p className="mt-2 text-sm text-text-muted">
                              Adicione o primeiro item para começar a montar esta seção do cardápio.
                            </p>
                            <Button
                              type="button"
                              className="mt-5"
                              onClick={() => openNewItemModal(selectedCategory.id)}
                            >
                              <Plus className="h-4 w-4" />
                              Criar item
                            </Button>
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-3xl border border-dashed border-border-color bg-dark px-6 text-center">
                      <Boxes className="h-10 w-10 text-text-muted" />
                      <p className="mt-4 text-base font-medium text-text-light">
                        Selecione uma categoria para ver os itens
                      </p>
                      <p className="mt-2 max-w-md text-sm leading-6 text-text-muted">
                        Você poderá adicionar itens, editar disponibilidade e cadastrar variáveis
                        extras assim que escolher ou criar uma categoria.
                      </p>
                    </div>
                  )}
                </section>
              </div>
            )}
          </div>
        </main>
      </div>

      {categoryForm && (
        <ModalFrame
          title={categoryForm.id ? 'Editar categoria' : 'Nova categoria'}
          description="Defina o nome da categoria e uma descrição opcional para organizar o cardápio."
          onClose={() => setCategoryForm(null)}
        >
          <form className="space-y-5" onSubmit={handleCategorySubmit}>
            <div className="space-y-2">
              <label className="text-sm font-medium text-text-light">Nome da categoria</label>
              <Input
                value={categoryForm.name}
                onChange={(event) =>
                  setCategoryForm((current) =>
                    current
                      ? {
                          ...current,
                          name: event.target.value,
                        }
                      : current
                  )
                }
                placeholder="Ex.: Sobremesas"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-text-light">Descrição</label>
              <textarea
                value={categoryForm.description}
                onChange={(event) =>
                  setCategoryForm((current) =>
                    current
                      ? {
                          ...current,
                          description: event.target.value,
                        }
                      : current
                  )
                }
                placeholder="Explique o que entra nesta categoria"
                rows={4}
                className="w-full rounded-2xl border border-border-color bg-dark px-4 py-3 text-sm text-text-light placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="flex justify-end gap-3">
              <Button type="button" variant="secondary" onClick={() => setCategoryForm(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? 'Salvando...' : categoryForm.id ? 'Salvar categoria' : 'Criar categoria'}
              </Button>
            </div>
          </form>
        </ModalFrame>
      )}

      {itemForm && (
        <ModalFrame
          title={itemForm.id ? 'Editar item' : 'Novo item'}
          description="Cadastre os dados principais do item e inclua variáveis livres sempre que precisar."
          onClose={() => setItemForm(null)}
        >
          <form className="space-y-5" onSubmit={handleItemSubmit}>
            <div className="grid gap-5 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-text-light">Nome do item</label>
                <Input
                  value={itemForm.name}
                  onChange={(event) =>
                    setItemForm((current) =>
                      current
                        ? {
                            ...current,
                            name: event.target.value,
                          }
                        : current
                    )
                  }
                  placeholder="Ex.: X-Burger"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-text-light">Preço</label>
                <Input
                  value={itemForm.price}
                  onChange={(event) =>
                    setItemForm((current) =>
                      current
                        ? {
                            ...current,
                            price: event.target.value,
                          }
                        : current
                    )
                  }
                  placeholder="Ex.: 24.90"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-text-light">Descrição</label>
              <textarea
                value={itemForm.description}
                onChange={(event) =>
                  setItemForm((current) =>
                    current
                      ? {
                          ...current,
                          description: event.target.value,
                        }
                      : current
                  )
                }
                placeholder="Conte um pouco sobre o item"
                rows={4}
                className="w-full rounded-2xl border border-border-color bg-dark px-4 py-3 text-sm text-text-light placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <label className="flex items-center gap-3 rounded-2xl border border-border-color bg-dark px-4 py-3">
              <input
                type="checkbox"
                checked={itemForm.is_available}
                onChange={(event) =>
                  setItemForm((current) =>
                    current
                      ? {
                          ...current,
                          is_available: event.target.checked,
                        }
                      : current
                  )
                }
                className="h-4 w-4 rounded border-border-color bg-dark text-primary focus:ring-primary"
              />
              <div>
                <p className="text-sm font-medium text-text-light">Item disponível</p>
                <p className="text-xs text-text-muted">
                  Desmarque se o item deve ficar temporariamente indisponível.
                </p>
              </div>
            </label>

            <div className="space-y-3 rounded-3xl border border-border-color bg-dark p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-text-light">Variáveis extras</p>
                  <p className="text-xs text-text-muted">
                    Ex.: tamanho, ponto da carne, observação, tempo médio.
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    setItemForm((current) =>
                      current
                        ? {
                            ...current,
                            custom_attributes: [...current.custom_attributes, { key: '', value: '' }],
                          }
                        : current
                    )
                  }
                >
                  <Plus className="h-4 w-4" />
                  Variável
                </Button>
              </div>

              <div className="space-y-3">
                {itemForm.custom_attributes.length ? (
                  itemForm.custom_attributes.map((attribute, index) => (
                    <div key={`${attribute.key}-${index}`} className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                      <Input
                        value={attribute.key}
                        onChange={(event) =>
                          setItemForm((current) =>
                            current
                              ? {
                                  ...current,
                                  custom_attributes: current.custom_attributes.map((currentAttribute, currentIndex) =>
                                    currentIndex === index
                                      ? { ...currentAttribute, key: event.target.value }
                                      : currentAttribute
                                  ),
                                }
                              : current
                          )
                        }
                        placeholder="Nome do campo"
                      />
                      <Input
                        value={attribute.value}
                        onChange={(event) =>
                          setItemForm((current) =>
                            current
                              ? {
                                  ...current,
                                  custom_attributes: current.custom_attributes.map((currentAttribute, currentIndex) =>
                                    currentIndex === index
                                      ? { ...currentAttribute, value: event.target.value }
                                      : currentAttribute
                                  ),
                                }
                              : current
                          )
                        }
                        placeholder="Valor"
                      />
                      <Button
                        type="button"
                        variant="secondary"
                        onClick={() =>
                          setItemForm((current) =>
                            current
                              ? {
                                  ...current,
                                  custom_attributes: current.custom_attributes.filter((_, currentIndex) => currentIndex !== index),
                                }
                              : current
                          )
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-text-muted">
                    Nenhuma variável cadastrada para este item.
                  </p>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button type="button" variant="secondary" onClick={() => setItemForm(null)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? 'Salvando...' : itemForm.id ? 'Salvar item' : 'Criar item'}
              </Button>
            </div>
          </form>
        </ModalFrame>
      )}
    </div>
  )
}
