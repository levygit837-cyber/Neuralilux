import { API_BASE_URL as API_URL } from '@/lib/constants'
import { apiRequest, clearServerSession, errorFromResponse } from '@/services/http'

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

export const authService = {
  /**
   * O backend grava o JWT num cookie `httpOnly` (`credentials: 'include'` deixa o navegador guardá-lo). O corpo
   * também traz o token, para scripts que não são navegador; o frontend não o lê nem o guarda.
   */
  async login(credentials: LoginCredentials): Promise<void> {
    const formData = new URLSearchParams()
    formData.append('username', credentials.email)
    formData.append('password', credentials.password)

    const response = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    })

    if (!response.ok) {
      throw new Error(await loginErrorMessage(response))
    }
  },

  /** Usuário da sessão (cookie). Um 401 passa pela camada HTTP central, que encerra a sessão. */
  getCurrentUser(): Promise<User> {
    return apiRequest<User>('/auth/me', {}, 'Erro ao obter dados do usuário')
  },

  /** Apaga o cookie de sessão no backend. Só ele pode: o cookie é `httpOnly`. */
  async logout(): Promise<void> {
    await clearServerSession()
  },

  async register(data: {
    email: string
    password: string
    full_name: string
  }): Promise<User> {
    const response = await fetch(`${API_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Erro ao registrar usuário')
    }

    return response.json()
  },
}
