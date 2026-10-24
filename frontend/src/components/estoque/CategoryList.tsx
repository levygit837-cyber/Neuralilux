import { PencilSimple, Plus, Tag, Trash } from '@phosphor-icons/react'

import { Button } from '@/components/ui/Button'
import type { MenuCategory } from '@/types/menu'

export function CategoryList({
  categories,
  selectedCategoryId,
  onSelect,
  onNew,
  onEdit,
  onDelete,
}: {
  categories: MenuCategory[] | undefined
  selectedCategoryId: string | null
  onSelect: (categoryId: string) => void
  onNew: () => void
  onEdit: (category: MenuCategory) => void
  onDelete: (category: MenuCategory) => void
}) {
  return (
    <section className="rounded-3xl border border-brand-border bg-brand-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-content-light">Categorias</p>
          <p className="text-xs text-content-muted">{categories?.length || 0} cadastradas</p>
        </div>
        <Button type="button" size="sm" onClick={onNew}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Adicionar
        </Button>
      </div>

      <div className="space-y-3">
        {categories?.length ? (
          categories.map((category) => {
            const isSelected = category.id === selectedCategoryId

            return (
              <div
                key={category.id}
                className={`relative w-full rounded-2xl border p-4 text-left transition-colors focus-within:ring-2 focus-within:ring-primary ${
                  isSelected
                    ? 'border-primary bg-primary/10'
                    : 'border-brand-border bg-brand-base hover:border-primary/40 hover:bg-brand-hover'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  {/* O botão cobre o card inteiro (after:inset-0); as ações ficam acima dele. */}
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => onSelect(category.id)}
                    className="cursor-pointer text-left after:absolute after:inset-0 after:rounded-2xl focus-visible:outline-none"
                  >
                    <span className="block font-medium text-content-light">{category.name}</span>
                    <span className="mt-1 block text-xs text-content-muted">
                      {category.items_count} item(ns)
                    </span>
                  </button>
                  <div className="relative z-10 flex items-center gap-2">
                    <button
                      type="button"
                      aria-label={`Editar categoria ${category.name}`}
                      onClick={() => onEdit(category)}
                      className="rounded-full bg-brand-hover p-2 text-content-muted hover:text-content-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                    >
                      <PencilSimple className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                    <button
                      type="button"
                      aria-label={`Excluir categoria ${category.name}`}
                      onClick={() => onDelete(category)}
                      className="rounded-full bg-brand-hover p-2 text-content-muted hover:text-status-error focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
                    >
                      <Trash className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </div>
                </div>

                {category.description && (
                  <p className="mt-3 text-sm leading-6 text-content-gray">
                    {category.description}
                  </p>
                )}
              </div>
            )
          })
        ) : (
          <div className="rounded-2xl border border-dashed border-brand-border bg-brand-base px-4 py-8 text-center">
            <Tag className="mx-auto h-8 w-8 text-content-muted" aria-hidden="true" />
            <p className="mt-4 text-sm font-medium text-content-light">
              Nenhuma categoria criada
            </p>
            <p className="mt-2 text-sm text-content-muted">
              Comece criando a primeira categoria do seu cardápio.
            </p>
            <Button type="button" size="sm" className="mt-4" onClick={onNew}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Criar categoria
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}
