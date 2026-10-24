import {
  SquaresFour,
  ChatCircleDots,
  Package,
  Receipt,
  DeviceMobile,
  SlidersHorizontal,
} from '@phosphor-icons/react'
import { ROUTES } from '@/lib/constants'

export const NAV_ITEMS = [
  { href: ROUTES.DASHBOARD, label: 'Dashboard', icon: SquaresFour },
  { href: ROUTES.CHAT, label: 'Chat', icon: ChatCircleDots },
  { href: ROUTES.INSTANCES, label: 'Instâncias', icon: DeviceMobile },
  { href: ROUTES.ORDERS, label: 'Pedidos', icon: Receipt },
  { href: ROUTES.STOCK, label: 'Estoque', icon: Package },
  { href: ROUTES.SETTINGS, label: 'Configurações', icon: SlidersHorizontal },
] as const
