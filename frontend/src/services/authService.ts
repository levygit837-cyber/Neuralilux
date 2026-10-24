import { apiFetch, apiRequest, clearServerSession, errorFromResponse, HttpError } from '@/services/http'
import type { User as SessionUser } from '@/types/auth'

export interface LoginCredentials {
  email: string
  password: string
}

export interface User {
  id: string
  email: string
  full_name: string
  company_id: string | null
  is_active: boolean
  is_superuser: boolean
  created_at: string
}

/**
 * Mensagem de um login recusado. 429 (rate limit por IP) diz quanto esperar, a partir de `Retry-After`;
 * 503 é o rate limit sem Redis (falha fechada). O resto vem do `detail` do backend.
 */
export async function loginErrorMessage(response: Response): Promise<string> {
  if (response.status === 429) {
    const seconds = Number(response.headers.get('Retry-After'))
    const wait = Number.isFinite(seconds) && seconds > 0 ? ` Tente de novo em ${Math.ceil(seconds)} s.` : ' Tente de novo em instantes.'
    return `Muitas tentativas de login.${wait}`
  }
  if (response.status === 503) return 'Login indisponível no momento. Tente de novo em instantes.'
  return (await errorFromResponse(response, 'Erro ao fazer login')).message
}

/** Usuário do store (nome e e-mail para a interface) a partir do `/auth/me`. */
export function toSessionUser(user: User): SessionUser {
  return { id: user.id, name: user.full_name || user.email, email: user.email }
}

export const authService = {
  /**
   * O backend grava o JWT num cookie `httpOnly` (`credentials: 'include'` deixa o navegador guardá-lo). Com `Origin`
   * (navegador) o corpo não traz o token; só scripts, sem `Origin`, o recebem. O frontend nunca o lê nem o guarda.
   */
  async login(credentials: LoginCredentials): Promise<void> {
    const formData = new URLSearchParams()
    formData.append('username', credentials.email)
    formData.append('password', credentials.password)

    // `apiFetch`, não `apiRequest`: 401 aqui é senha errada, e `apiRequest` encerraria uma sessão que não existe.
    const response = await apiFetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    })

    if (!response.ok) throw new HttpError(response.status, await loginErrorMessage(response))
  },

  /** Usuário da sessão (cookie). Um 401 passa pela camada HTTP central, que encerra a sessão. */
  getCurrentUser(): Promise<User> {
    return apiRequest<User>('/auth/me', {}, 'Erro ao obter dados do usuário')
  },

  /**
   * Apaga o cookie de sessão no backend. Só ele pode: o cookie é `httpOnly`. Recusa (403 por `CORS_ORIGINS`, 5xx)
   * vira erro: o cookie continua valendo, então quem chama não pode dar a sessão por encerrada.
   */
  async logout(): Promise<void> {
    const response = await clearServerSession()
    if (!response.ok) throw await errorFromResponse(response, 'Erro ao encerrar a sessão')
  },
}
