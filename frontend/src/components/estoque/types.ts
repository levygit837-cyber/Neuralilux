import type { MenuAttribute } from '@/types/menu'

export type CategoryFormState = {
  id: string | null
  name: string
  description: string
}

export type ItemFormState = {
  id: string | null
  category_id: string
  name: string
  description: string
  price: string
  is_available: boolean
  custom_attributes: MenuAttribute[]
}
