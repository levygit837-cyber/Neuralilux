import type { Dispatch, FormEvent, SetStateAction } from 'react'
import { Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

import { ModalFrame } from './ModalFrame'
import type { ItemFormState } from './types'

export function ItemFormDialog({
  itemForm,
  setItemForm,
  isSaving,
  onSubmit,
}: {
  itemForm: ItemFormState
  setItemForm: Dispatch<SetStateAction<ItemFormState | null>>
  isSaving: boolean
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <ModalFrame
      title={itemForm.id ? 'Editar item' : 'Novo item'}
      description="Cadastre os dados principais do item e inclua variáveis livres sempre que precisar."
      onClose={() => setItemForm(null)}
    >
      <form className="space-y-5" onSubmit={onSubmit}>
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
  )
}
