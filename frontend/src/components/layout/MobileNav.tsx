'use client'

import { useEffect, useRef } from 'react'
import { usePathname } from 'next/navigation'
import { List, X } from '@phosphor-icons/react'
import { Brand } from './Brand'
import { NavList } from './NavList'

/**
 * Barra superior e drawer da navegação abaixo de 1024px. O drawer usa `<dialog>` modal:
 * o navegador prende o foco, fecha com Esc e devolve o foco ao botão que o abriu.
 */
export function MobileNav() {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const pathname = usePathname()

  useEffect(() => {
    dialogRef.current?.close()
  }, [pathname])

  // O drawer não existe a partir de `lg`: um dialog modal aberto ali prenderia o foco atrás da Sidebar.
  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 1024px)')
    const closeOnDesktop = (event: MediaQueryListEvent) => {
      if (event.matches) dialogRef.current?.close()
    }
    desktop.addEventListener('change', closeOnDesktop)
    return () => desktop.removeEventListener('change', closeOnDesktop)
  }, [])

  const close = () => dialogRef.current?.close()

  return (
    <div className="flex h-14 shrink-0 items-center gap-3 border-b border-brand-border bg-brand-card/80 px-4 lg:hidden">
      <button
        type="button"
        aria-label="Abrir menu"
        aria-haspopup="dialog"
        onClick={() => dialogRef.current?.showModal()}
        className="flex h-10 w-10 items-center justify-center rounded-lg border border-brand-border text-content-light hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
      >
        <List className="text-xl" aria-hidden="true" />
      </button>
      <Brand />

      {/* Clique no backdrop é atalho para mouse/toque; teclado fecha com Esc ou pelo botão "Fechar menu". */}
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions */}
      <dialog
        ref={dialogRef}
        aria-label="Menu de navegação"
        onClick={(event) => {
          if (event.target === event.currentTarget) close()
        }}
        className="m-0 h-full max-h-none w-72 max-w-[85vw] border-r border-brand-border bg-brand-card p-0 text-content-light backdrop:bg-black/60"
      >
        <div className="flex h-full flex-col">
          <div className="flex h-14 items-center justify-between border-b border-brand-border/50 px-4">
            <Brand />
            <button
              type="button"
              aria-label="Fechar menu"
              onClick={close}
              className="flex h-10 w-10 items-center justify-center rounded-lg text-content-muted hover:text-content-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
            >
              <X className="text-xl" aria-hidden="true" />
            </button>
          </div>
          <NavList onNavigate={close} />
        </div>
      </dialog>
    </div>
  )
}
