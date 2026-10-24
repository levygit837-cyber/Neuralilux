import { Stack, CurrencyCircleDollar, Package, PencilSimple, Plus, Trash } from '@phosphor-icons/react'

import { Button } from '@/components/ui/Button'
import type { MenuCategory, MenuItem } from '@/types/menu'

import { formatPrice } from './helpers'

export function ItemList({
  selectedCategory,
  categoryItems,
  onNewItem,
  onEditItem,
  onDeleteItem,
}: {
  selectedCategory: MenuCategory | null
  categoryItems: MenuItem[]
  onNewItem: (categoryId: string) => void
  onEditItem: (item: MenuItem) => void
  onDeleteItem: (item: MenuItem) => void
}) {
  return (
    <section className="rounded-3xl border border-brand-border bg-brand-card p-5">
      {selectedCategory ? (
        <>
          <div className="mb-5 flex flex-col gap-4 border-b border-brand-border pb-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h3 className="text-2xl font-semibold text-content-light">
                {selectedCategory.name}
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-content-muted">
                {selectedCategory.description ||
                  'Use esta categoria para concentrar itens parecidos e manter o cardápio organizado.'}
              </p>
            </div>
            <Button type="button" onClick={() => onNewItem(selectedCategory.id)}>
              <Package className="h-4 w-4" aria-hidden="true" />
              Novo item
            </Button>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            {categoryItems.length ? (
              categoryItems.map((item) => (
                <article
                  key={item.id}
                  className="rounded-3xl border border-brand-border bg-brand-base p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-lg font-semibold text-content-light">
                          {item.name}
                        </h4>
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                            item.is_available
                              ? 'bg-status-success/15 text-status-success'
                              : 'bg-status-warning/15 text-status-warning'
                          }`}
                        >
                          {item.is_available ? 'Disponível' : 'Indisponível'}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-content-gray">
                        <CurrencyCircleDollar className="h-4 w-4 text-primary-light" aria-hidden="true" />
                        {formatPrice(item.price)}
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => onEditItem(item)}
                        className="rounded-full bg-brand-hover p-2 text-content-muted hover:text-content-light"
                      >
                        <PencilSimple className="h-4 w-4" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteItem(item)}
                        className="rounded-full bg-brand-hover p-2 text-content-muted hover:text-status-error"
                      >
                        <Trash className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  </div>

                  <p className="mt-4 text-sm leading-6 text-content-gray">
                    {item.description || 'Sem descrição cadastrada.'}
                  </p>

                  <div className="mt-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-content-muted">
                      Variáveis extras
                    </p>
                    {item.custom_attributes.length ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {item.custom_attributes.map((attribute, index) => (
                          <span
                            key={`${attribute.key}-${index}`}
                            className="rounded-full border border-brand-border bg-brand-card px-3 py-1.5 text-xs text-content-gray"
                          >
                            <strong className="text-content-light">{attribute.key}:</strong>{' '}
                            {attribute.value}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 text-sm text-content-muted">
                        Este item ainda não tem variáveis extras.
                      </p>
                    )}
                  </div>
                </article>
              ))
            ) : (
              <div className="rounded-3xl border border-dashed border-brand-border bg-brand-base px-6 py-12 text-center xl:col-span-2">
                <Package className="mx-auto h-9 w-9 text-content-muted" aria-hidden="true" />
                <p className="mt-4 text-sm font-medium text-content-light">
                  Nenhum item nesta categoria
                </p>
                <p className="mt-2 text-sm text-content-muted">
                  Adicione o primeiro item para começar a montar esta seção do cardápio.
                </p>
                <Button
                  type="button"
                  className="mt-5"
                  onClick={() => onNewItem(selectedCategory.id)}
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Criar item
                </Button>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-3xl border border-dashed border-brand-border bg-brand-base px-6 text-center">
          <Stack className="h-10 w-10 text-content-muted" aria-hidden="true" />
          <p className="mt-4 text-base font-medium text-content-light">
            Selecione uma categoria para ver os itens
          </p>
          <p className="mt-2 max-w-md text-sm leading-6 text-content-muted">
            Você poderá adicionar itens, editar disponibilidade e cadastrar variáveis
            extras assim que escolher ou criar uma categoria.
          </p>
        </div>
      )}
    </section>
  )
}
