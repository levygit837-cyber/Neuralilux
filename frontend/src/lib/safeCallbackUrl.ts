import { POST_LOGIN_ROUTE } from '@/lib/constants'

const ORIGIN_PROBE = 'http://callback.invalid'

/**
 * Destino pós-login vindo de `?callbackUrl=`. Só aceita path interno relativo
 * (`/chat?x=1`); qualquer outra coisa (URL absoluta, `//host`, `\`, `/login`) cai no padrão.
 */
export function safeCallbackUrl(raw: string | string[] | null | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (!value || !value.startsWith('/') || value.startsWith('//') || /[\\\u0000-\u001f]/.test(value)) {
    return POST_LOGIN_ROUTE
  }
  try {
    const url = new URL(value, ORIGIN_PROBE)
    if (url.origin !== ORIGIN_PROBE || url.pathname === '/login' || url.pathname.startsWith('/login/')) {
      return POST_LOGIN_ROUTE
    }
  } catch {
    return POST_LOGIN_ROUTE
  }
  return value
}
