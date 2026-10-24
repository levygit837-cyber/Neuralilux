'use client'

import { Stack, Plus } from '@phosphor-icons/react'

import { CategoryFormDialog } from '@/components/estoque/CategoryFormDialog'
import { CategoryList } from '@/components/estoque/CategoryList'
import { ItemFormDialog } from '@/components/estoque/ItemFormDialog'
import { ItemList } from '@/components/estoque/ItemList'
import { Button } from '@/components/ui/Button'
import { useMenuManagement } from '@/hooks/useMenuManagement'

export default function EstoquePage() {
  const {
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
  } = useMenuManagement()

  return (
    <div className="p-4 sm:p-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="rounded-3xl border border-brand-border bg-brand-card p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-primary-light">
                <Stack className="h-3.5 w-3.5" aria-hidden="true" />
                Estoque conectado ao cardápio
              </div>
              <h2 className="text-3xl font-semibold text-content-light">
                Organize categorias, itens e variáveis do seu cardápio
              </h2>
              <p className="max-w-3xl text-sm leading-6 text-content-muted">
                Cadastre novas categorias, adicione itens, marque disponibilidade e mantenha
                atributos livres por produto para deixar o cardápio mais completo.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {menu?.catalog && (
                <div className="rounded-2xl border border-brand-border bg-brand-base px-4 py-3 text-sm text-content-gray">
                  <p className="font-medium text-content-light">{menu.catalog.name}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-content-muted">
                    Fonte {menu.catalog.source_type === 'manual' ? 'manual' : 'importada'}
                  </p>
                </div>
              )}
              <Button type="button" onClick={openNewCategoryModal}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                Nova categoria
              </Button>
            </div>
          </div>
        </section>

        {displayedError && (
          <div className="rounded-2xl border border-status-error/30 bg-status-error/10 px-4 py-3 text-sm text-status-error">
            {displayedError}
          </div>
        )}

        {showSkeleton ? (
          <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
            <div className="h-[520px] animate-pulse rounded-3xl bg-brand-card" />
            <div className="h-[520px] animate-pulse rounded-3xl bg-brand-card" />
          </div>
        ) : (
          <div className="grid min-h-0 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
            <CategoryList
              categories={menu?.categories}
              selectedCategoryId={selectedCategoryId}
              onSelect={setSelectedCategoryId}
              onNew={openNewCategoryModal}
              onEdit={openEditCategoryModal}
              onDelete={(category) => void handleDeleteCategory(category)}
            />
            <ItemList
              selectedCategory={selectedCategory}
              categoryItems={categoryItems}
              onNewItem={openNewItemModal}
              onEditItem={openEditItemModal}
              onDeleteItem={(item) => void handleDeleteItem(item)}
            />
          </div>
        )}
      </div>

      {categoryForm && (
        <CategoryFormDialog
          categoryForm={categoryForm}
          setCategoryForm={setCategoryForm}
          isSaving={isSaving}
          onSubmit={handleCategorySubmit}
        />
      )}

      {itemForm && (
        <ItemFormDialog
          itemForm={itemForm}
          setItemForm={setItemForm}
          isSaving={isSaving}
          onSubmit={handleItemSubmit}
        />
      )}
    </div>
  )
}
