import { API_INTERNAL_URL, AUTH_COOKIE_NAME } from '@/lib/constants'

const SESSION_CHECK_TIMEOUT_MS = 3000

/** `valid`: o backend aceitou o cookie. `invalid`: recusou (forjado, vencido, usuário inativo). `unavailable`: sem resposta. */
export type SessionState = 'none' | 'valid' | 'invalid' | 'unavailable'

/**
 * A sessão só vale se o backend a aceitar: o Next não lê nem decodifica o JWT, entrega o cookie ao `/auth/me`,
 * que verifica assinatura, prazo e se o usuário segue ativo. Cookie forjado, vencido ou de usuário desativado não passa.
 * Só roda no servidor (proxy e layout `(app)`).
 */
export async function checkSession(cookie: string | undefined): Promise<SessionState> {
  if (!cookie) return 'none'
  try {
    const response = await fetch(`${API_INTERNAL_URL}/api/v1/auth/me`, {
      headers: { Cookie: `${AUTH_COOKIE_NAME}=${cookie}` },
      cache: 'no-store',
      signal: AbortSignal.timeout(SESSION_CHECK_TIMEOUT_MS),
    })
    if (response.ok) return 'valid'
    return response.status === 401 ? 'invalid' : 'unavailable'
  } catch {
    return 'unavailable'
  }
}
