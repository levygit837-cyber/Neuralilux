'use client'

import { useEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'

interface DialogProps {
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
}

/**
 * Último controle tocado ou focado. No Safari, clicar em um botão não o foca: `document.activeElement`
 * vira o `body` e o foco não teria para onde voltar. O `pointerdown` cobre esse caso.
 */
let lastInteracted: HTMLElement | null = null

function remember(event: Event) {
  if (!(event.target instanceof Element)) return
  lastInteracted = event.target.closest<HTMLElement>('button, a[href], input, select, textarea, summary, [tabindex]')
}

if (typeof document !== 'undefined') {
  document.addEventListener('pointerdown', remember, true)
  document.addEventListener('focusin', remember, true)
}

/**
 * Único primitivo de modal. Usa `<dialog>` nativo com `showModal()`: o navegador prende o foco,
 * fecha com Esc e move o foco para dentro. O pai monta o Dialog para abrir e o desmonta em
 * `onClose` para fechar; ao desmontar, o foco volta ao controle que o abriu.
 */
export function Dialog({ onClose, title, description, children }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    const active = document.activeElement
    const opener = active instanceof HTMLElement && active !== document.body ? active : lastInteracted
    dialog.showModal()
    // `showModal()` foca o primeiro controle (o "Fechar"). O React chama `.focus()` no commit, com o <dialog>
    // ainda fechado, então `autoFocus` não funciona aqui: o campo inicial leva `data-autofocus`.
    dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus()
    return () => {
      dialog.close()
      if (opener?.isConnected) opener.focus()
    }
  }, [])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        // Esc: quem fecha é o pai, desmontando o Dialog.
        event.preventDefault()
        onClose()
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-2xl rounded-3xl border border-border-color bg-card p-0 text-text-light shadow-2xl backdrop:bg-dark/80 backdrop:backdrop-blur-sm"
    >
      <div className="flex max-h-[90vh] flex-col">
        <div className="flex items-start justify-between border-b border-border-color px-6 py-5">
          <div>
            <h2 id={titleId} className="text-xl font-semibold text-text-light">
              {title}
            </h2>
            {description && (
              <p id={descriptionId} className="mt-1 text-sm text-text-muted">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label="Fechar"
            onClick={onClose}
            className="rounded-full bg-hover p-2 text-text-muted transition-colors hover:bg-border-color hover:text-text-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-6">{children}</div>
      </div>
    </dialog>
  )
}
