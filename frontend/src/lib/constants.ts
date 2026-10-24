export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
// O Socket.IO é do nosso backend: sem NEXT_PUBLIC_WS_URL, usa o mesmo host da API.
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || API_BASE_URL.replace(/^http/i, 'ws')

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  STOCK: '/estoque',
  ORDERS: '/pedidos',
  CHAT: '/chat',
  QR: '/qr',
  INSTANCES: '/instances',
  SETTINGS: '/settings',
} as const

// Único destino após login (e para quem já está autenticado em /login ou /).
export const POST_LOGIN_ROUTE = ROUTES.DASHBOARD

export const POLLING_INTERVAL = 3000 // 3 seconds for polling fallback
export const MESSAGE_PAGE_SIZE = 50
export const CONVERSATION_PAGE_SIZE = 100
