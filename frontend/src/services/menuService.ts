import { API_BASE_URL } from '@/lib/constants'
import type {
  MenuCategoryPayload,
  MenuCategory,
  MenuItem,
  MenuItemPayload,
  MenuManagementPayload,
} from '@/types/menu'

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(init?.headers || {}),
    },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.detail || 'Erro ao carregar estoque')
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export const menuService = {
  getMenu(token: string): Promise<MenuManagementPayload> {
    return request<MenuManagementPayload>('/menu', token, { method: 'GET' })
  },

  createCategory(token: string, payload: MenuCategoryPayload): Promise<MenuCategory> {
    return request<MenuCategory>('/menu/categories', token, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  updateCategory(token: string, categoryId: string, payload: Partial<MenuCategoryPayload>): Promise<MenuCategory> {
    return request<MenuCategory>(`/menu/categories/${categoryId}`, token, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  deleteCategory(token: string, categoryId: string): Promise<void> {
    return request<void>(`/menu/categories/${categoryId}`, token, {
      method: 'DELETE',
    })
  },

  createItem(token: string, payload: MenuItemPayload): Promise<MenuItem> {
    return request<MenuItem>('/menu/items', token, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  updateItem(token: string, itemId: string, payload: Partial<MenuItemPayload>): Promise<MenuItem> {
    return request<MenuItem>(`/menu/items/${itemId}`, token, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  deleteItem(token: string, itemId: string): Promise<void> {
    return request<void>(`/menu/items/${itemId}`, token, {
      method: 'DELETE',
    })
  },
}
