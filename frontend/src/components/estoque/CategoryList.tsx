import { Pencil, Plus, Tag, Trash2 } from 'lucide-react'

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
    <section className="rounded-3xl border border-border-color bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-text-light">Categorias</p>
          <p className="text-xs text-text-muted">{categories?.length || 0} cadastradas</p>
        </div>
        <Button type="button" size="sm" onClick={onNew}>
          <Plus className="h-4 w-4" />
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
                onClick={() => onSelect(category.id)}
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
                        onEdit(category)
                      }}
                      className="rounded-full bg-hover p-2 text-text-muted hover:text-text-light"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        onDelete(category)
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
            <Button type="button" size="sm" className="mt-4" onClick={onNew}>
              <Plus className="h-4 w-4" />
              Criar categoria
            </Button>
          </div>
        )}
      </div>
    </section>
  )
}
