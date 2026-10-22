import { apiRequest, jsonBody } from '@/services/http'
import type {
  MenuCategoryPayload,
  MenuCategory,
  MenuItem,
  MenuItemPayload,
  MenuManagementPayload,
} from '@/types/menu'

const FALLBACK = 'Erro ao carregar estoque'

function request<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, init, FALLBACK)
}

export const menuService = {
  getMenu(): Promise<MenuManagementPayload> {
    return request<MenuManagementPayload>('/menu', { method: 'GET' })
  },

  createCategory(payload: MenuCategoryPayload): Promise<MenuCategory> {
    return request<MenuCategory>('/menu/categories', jsonBody('POST', payload))
  },

  updateCategory(categoryId: string, payload: Partial<MenuCategoryPayload>): Promise<MenuCategory> {
    return request<MenuCategory>(`/menu/categories/${categoryId}`, jsonBody('PATCH', payload))
  },

  deleteCategory(categoryId: string): Promise<void> {
    return request<void>(`/menu/categories/${categoryId}`, { method: 'DELETE' })
  },

  createItem(payload: MenuItemPayload): Promise<MenuItem> {
    return request<MenuItem>('/menu/items', jsonBody('POST', payload))
  },

  updateItem(itemId: string, payload: Partial<MenuItemPayload>): Promise<MenuItem> {
    return request<MenuItem>(`/menu/items/${itemId}`, jsonBody('PATCH', payload))
  },

  deleteItem(itemId: string): Promise<void> {
    return request<void>(`/menu/items/${itemId}`, { method: 'DELETE' })
  },
}
