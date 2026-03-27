export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

export const ROUTES = {
  HOME: '/',
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  CHAT: '/chat',
  QR: '/qr',
  INSTANCES: '/instances',
} as const

export const POLLING_INTERVAL = 3000 // 3 seconds for polling fallback
export const TYPING_TIMEOUT = 3000
export const MESSAGE_PAGE_SIZE = 50
