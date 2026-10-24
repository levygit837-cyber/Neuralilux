// @vitest-environment jsdom
import { useState } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { Dialog } from '@/components/ui/Dialog'

// O jsdom não implementa showModal/close. Este polyfill reproduz o que o navegador faz:
// marca o dialog como aberto e move o foco para dentro dele.
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
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
          <input id="nome" />
        </Dialog>
      )}
    </>
  )
}

describe('Dialog', () => {
  it('abre com o foco dentro, nomeado pelo título', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByRole('button', { name: 'Abrir' }))

    const dialog = screen.getByRole('dialog', { name: 'Nova categoria' })
    expect(dialog.contains(document.activeElement)).toBe(true)
    expect(dialog.getAttribute('aria-describedby')).not.toBeNull()
  })

  it('Escape fecha e devolve o foco ao botão que abriu', async () => {
    const user = userEvent.setup()
    render(<Harness />)
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
    render(<Harness />)
    const opener = screen.getByRole('button', { name: 'Abrir' })
    await user.click(opener)

    await user.click(screen.getByRole('button', { name: 'Fechar' }))

    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })
})
