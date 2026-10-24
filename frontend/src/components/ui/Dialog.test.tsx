// @vitest-environment jsdom
import { StrictMode, useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { Dialog } from '@/components/ui/Dialog'

// O jsdom não implementa showModal/close. Este polyfill segue o navegador no que importa aqui:
// showModal() num dialog já aberto lança InvalidStateError e move o foco para dentro.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    if (this.hasAttribute('open')) throw new DOMException('O dialog já está aberto.', 'InvalidStateError')
    this.setAttribute('open', '')
    this.querySelector<HTMLElement>('input, textarea, select, button')?.focus()
  }
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    this.removeAttribute('open')
  }
})

afterEach(cleanup)

function Harness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Abrir
      </button>
      {open && (
        <Dialog title="Nova categoria" description="Preencha o nome." onClose={() => setOpen(false)}>
          <label htmlFor="nome">Nome</label>
          <input id="nome" data-autofocus />
        </Dialog>
      )}
    </>
  )
}

// StrictMode monta, desmonta e monta de novo os efeitos: é o que pega um Dialog que não fecha no cleanup.
const renderHarness = () =>
  render(
    <StrictMode>
      <Harness />
    </StrictMode>
  )

describe('Dialog', () => {
  it('abre com o foco dentro, nomeado pelo título, mesmo com mount → cleanup → mount', async () => {
    const user = userEvent.setup()
    renderHarness()

    await user.click(screen.getByRole('button', { name: 'Abrir' }))

    const dialog = screen.getByRole('dialog', { name: 'Nova categoria' })
    expect(dialog.contains(document.activeElement)).toBe(true)
    expect(dialog.getAttribute('aria-describedby')).not.toBeNull()
  })

  it('o foco inicial vai para o campo marcado com data-autofocus, não para o botão Fechar', async () => {
    const user = userEvent.setup()
    renderHarness()

    await user.click(screen.getByRole('button', { name: 'Abrir' }))

    expect(document.activeElement).toBe(screen.getByLabelText('Nome'))
  })

  it('Escape fecha e devolve o foco ao botão que abriu', async () => {
    const user = userEvent.setup()
    renderHarness()
    const opener = screen.getByRole('button', { name: 'Abrir' })
    await user.click(opener)
    const dialog = screen.getByRole('dialog', { name: 'Nova categoria' })

    // Esc dispara `cancel` no <dialog>; o navegador faz isso, o jsdom não.
    fireEvent(dialog, new Event('cancel', { cancelable: true }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('o botão Fechar tem nome acessível, fecha e devolve o foco', async () => {
    const user = userEvent.setup()
    renderHarness()
    const opener = screen.getByRole('button', { name: 'Abrir' })
    await user.click(opener)

    await user.click(screen.getByRole('button', { name: 'Fechar' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('devolve o foco ao botão mesmo quando o clique não o focou (Safari)', () => {
    renderHarness()
    const opener = screen.getByRole('button', { name: 'Abrir' })
    // No Safari, clicar num botão não o foca: o activeElement continua sendo o body.
    expect(document.activeElement).toBe(document.body)

    fireEvent.pointerDown(opener)
    fireEvent.click(opener)
    const dialog = screen.getByRole('dialog', { name: 'Nova categoria' })
    expect(document.activeElement).not.toBe(opener)

    fireEvent(dialog, new Event('cancel', { cancelable: true }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })
})
