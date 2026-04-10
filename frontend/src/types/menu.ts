export interface MenuAttribute {
  key: string
  value: string
}

export interface MenuCatalog {
  id: string
  name: string
  source_type: string | null
}

export interface MenuCategory {
  id: string
  name: string
  description: string | null
  sort_order: number
  items_count: number
  created_at: string
  updated_at: string | null
}

export interface MenuItem {
  id: string
  category_id: string
  name: string
  description: string | null
  price: number | string | null
  is_available: boolean
  custom_attributes: MenuAttribute[]
  created_at: string
  updated_at: string | null
}

export interface MenuManagementPayload {
  catalog: MenuCatalog
  categories: MenuCategory[]
  items: MenuItem[]
}

export interface MenuCategoryPayload {
  name: string
  description?: string | null
}

export interface MenuItemPayload {
  category_id: string
  name: string
  description?: string | null
  price?: string | number | null
  is_available?: boolean
  custom_attributes?: MenuAttribute[]
}
