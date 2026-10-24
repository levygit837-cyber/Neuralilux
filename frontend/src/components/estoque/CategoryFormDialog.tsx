import type { Dispatch, FormEvent, SetStateAction } from 'react'

import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

import { Dialog } from '@/components/ui/Dialog'
import type { CategoryFormState } from './types'

export function CategoryFormDialog({
  categoryForm,
  setCategoryForm,
  isSaving,
  onSubmit,
}: {
  categoryForm: CategoryFormState
  setCategoryForm: Dispatch<SetStateAction<CategoryFormState | null>>
  isSaving: boolean
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <Dialog
      title={categoryForm.id ? 'Editar categoria' : 'Nova categoria'}
      description="Defina o nome da categoria e uma descrição opcional para organizar o cardápio."
      onClose={() => setCategoryForm(null)}
    >
      <form className="space-y-5" onSubmit={onSubmit}>
        <div className="space-y-2">
          <label htmlFor="category-name" className="text-sm font-medium text-text-light">Nome da categoria</label>
          <Input
            id="category-name"
            data-autofocus
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
          <label htmlFor="category-description" className="text-sm font-medium text-text-light">Descrição</label>
          <textarea
            id="category-description"
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
    </Dialog>
  )
}
