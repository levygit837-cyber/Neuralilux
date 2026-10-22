import { API_BASE_URL } from '@/lib/constants'

/** Erro de uma chamada ao backend. `detail` é a mensagem do FastAPI quando ela vem como texto. */
export class HttpError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
  }
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
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') message = body.detail
  } catch {
    /* corpo sem JSON */
  }
  return new HttpError(response.status, message)
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

  if (!response.ok) throw await errorFromResponse(response, fallback)
  if (response.status === 204) return undefined as T
  return response.json()
}

export const jsonBody = (method: string, body: unknown): RequestInit => ({
  method,
  body: JSON.stringify(body),
})
