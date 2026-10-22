import { API_BASE_URL, ROUTES } from '@/lib/constants'
import { useAuthStore } from '@/stores/useAuthStore'

/**
 * Erro de uma chamada ao backend. `message` vem do `detail` do FastAPI; num 422 com lista de
 * erros, `fieldErrors` traz a primeira mensagem por campo do corpo.
 */
export class HttpError extends Error {
  readonly status: number
  readonly fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

interface ValidationItem {
  loc?: unknown[]
  msg?: string
}

function parseValidationErrors(items: ValidationItem[]): { message?: string; fieldErrors: Record<string, string> } {
  const messages: string[] = []
  const fieldErrors: Record<string, string> = {}
  for (const item of items) {
    if (!item.msg) continue
    // O pydantic prefixa erros de validators próprios com "Value error, ".
    const text = item.msg.replace(/^Value error, /, '')
    messages.push(text)
    const field = item.loc?.[item.loc.length - 1]
    if (typeof field === 'string' && !(field in fieldErrors)) fieldErrors[field] = text
  }
  return { message: messages.length > 0 ? messages.join('; ') : undefined, fieldErrors }
}

export function getToken(): string | null {
  return typeof window !== 'undefined' ? localStorage.getItem('token') : null
}

/** Cabeçalho `Authorization: Bearer` do usuário logado; vazio quando não há token. */
export function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function errorFromResponse(response: Response, fallback?: string): Promise<HttpError> {
  let message = fallback ?? `Erro ${response.status}`
  let fieldErrors: Record<string, string> = {}
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') {
      message = body.detail
    } else if (Array.isArray(body?.detail)) {
      const parsed = parseValidationErrors(body.detail)
      message = parsed.message ?? message
      fieldErrors = parsed.fieldErrors
    }
  } catch {
    /* corpo sem JSON */
  }
  return new HttpError(response.status, message, fieldErrors)
}

/** Token recusado: encerra a sessão pelo mesmo caminho do logout e leva para o login. */
function endSession(): void {
  useAuthStore.getState().logout()
  if (typeof window !== 'undefined' && window.location.pathname !== ROUTES.LOGIN) {
    window.location.assign(ROUTES.LOGIN)
  }
}

/**
 * Chamada JSON autenticada ao backend (`/api/v1` + `path`). É a única porta do frontend para
 * dados: nenhuma chave de terceiros passa por aqui, só o Bearer do usuário.
 * `init.headers` vence os padrões (ex.: login ainda sem token salvo).
 */
export async function apiRequest<T>(path: string, init: RequestInit = {}, fallback?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...init,
    headers: {
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...authHeaders(),
      ...(init.headers as Record<string, string> | undefined),
    },
  })

  if (!response.ok) {
    if (response.status === 401) endSession()
    throw await errorFromResponse(response, fallback)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export const jsonBody = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
})
