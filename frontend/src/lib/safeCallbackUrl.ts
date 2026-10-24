import { POST_LOGIN_ROUTE, ROUTES } from '@/lib/constants'

const ORIGIN_PROBE = 'http://callback.invalid'
const UNSAFE_CHARS = /[\s\\\u0000-\u001f]/

/**
 * Destino pós-login vindo de `?callbackUrl=`. Só aceita path interno relativo
 * (`/chat?x=1`). Cai em `POST_LOGIN_ROUTE` para qualquer outra coisa: URL absoluta, `//host`,
 * `\`, espaço ou controle (também depois de decodificar `%2F`/`%5C`), `/login` e a própria `/`
 * (que o proxy redirecionaria de novo).
 */
export function safeCallbackUrl(raw: string | string[] | null | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (!value || !value.startsWith('/')) return POST_LOGIN_ROUTE

  let decoded: string
  try {
    decoded = decodeURIComponent(value)
  } catch {
    return POST_LOGIN_ROUTE
  }
  if (decoded.startsWith('//') || UNSAFE_CHARS.test(value) || UNSAFE_CHARS.test(decoded)) {
    return POST_LOGIN_ROUTE
  }

  try {
    const url = new URL(value, ORIGIN_PROBE)
    const isLoginOrHome =
      url.pathname === ROUTES.HOME || url.pathname === ROUTES.LOGIN || url.pathname.startsWith(`${ROUTES.LOGIN}/`)
    if (url.origin !== ORIGIN_PROBE || isLoginOrHome) return POST_LOGIN_ROUTE
  } catch {
    return POST_LOGIN_ROUTE
  }
  return value
}
