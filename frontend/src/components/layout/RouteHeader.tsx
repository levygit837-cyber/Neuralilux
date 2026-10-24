'use client'

import { usePathname } from 'next/navigation'
import { ROUTES } from '@/lib/constants'
import { Header } from './Header'

// Chat e Configurações têm cabeçalho próprio no conteúdo.
const HEADERS: Record<string, { title: string; showOnlineBadge: boolean }> = {
  [ROUTES.DASHBOARD]: { title: 'Dashboard', showOnlineBadge: true },
  [ROUTES.INSTANCES]: { title: 'Instâncias', showOnlineBadge: false },
  [ROUTES.ORDERS]: { title: 'Pedidos', showOnlineBadge: true },
  [ROUTES.STOCK]: { title: 'Estoque', showOnlineBadge: true },
  [ROUTES.QR]: { title: 'QR Code', showOnlineBadge: true },
}

export function RouteHeader() {
  const pathname = usePathname()
  const config = HEADERS[`/${pathname.split('/')[1]}`]
  if (!config) return null
  return <Header title={config.title} showOnlineBadge={config.showOnlineBadge} />
}
