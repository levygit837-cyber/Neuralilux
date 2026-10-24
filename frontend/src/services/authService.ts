import { API_BASE_URL as API_URL } from '@/lib/constants'
import { apiRequest } from '@/services/http'

export interface LoginCredentials {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
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

export const authService = {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    const formData = new URLSearchParams()
    formData.append('username', credentials.email)
    formData.append('password', credentials.password)

    const response = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Erro ao fazer login')
    }

    return response.json()
  },

  /** `token` explícito: no login o token ainda não está salvo. Um 401 passa pela camada HTTP central. */
  getCurrentUser(token: string): Promise<User> {
    return apiRequest<User>('/auth/me', { headers: { Authorization: `Bearer ${token}` } }, 'Erro ao obter dados do usuário')
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
