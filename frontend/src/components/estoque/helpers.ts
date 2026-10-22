import type { MenuAttribute, MenuItem } from '@/types/menu'

export function formatPrice(price: MenuItem['price']): string {
  if (price === null || price === undefined || price === '') {
    return 'Sem preço'
  }

  const numericPrice = Number(price)
  if (Number.isNaN(numericPrice)) {
    return String(price)
  }

  return numericPrice.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
}

export function normalizeCustomAttributes(customAttributes: MenuAttribute[]): MenuAttribute[] {
  return customAttributes
    .map((attribute) => ({
      key: attribute.key.trim(),
      value: attribute.value.trim(),
    }))
    .filter((attribute) => attribute.key && attribute.value)
}
