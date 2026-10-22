import { apiRequest } from '@/services/http'
import type {
  MenuCategoryPayload,
  MenuCategory,
  MenuItem,
  MenuItemPayload,
  MenuManagementPayload,
} from '@/types/menu'

function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, { ...init, headers: { Authorization: `Bearer ${token}` } }, 'Erro ao carregar estoque')
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
