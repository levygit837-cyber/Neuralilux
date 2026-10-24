import { notFound } from 'next/navigation'

// URL sem rota dentro da área autenticada: sem isto, o Next usaria o 404 da raiz, sem Sidebar.
export default function UnknownRoute(): never {
  notFound()
}
