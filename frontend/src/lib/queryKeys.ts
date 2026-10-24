import type { OrderListFilter } from '@/types/order'

/**
 * Chaves de query por recurso. Company e Agent levam o id da Company na chave; as demais não
 * carregam usuário. O isolamento entre sessões vem de `clearQueryCache()`, chamado no login e no
 * logout (inclusive o do 401), não da chave.
 */
export const queryKeys = {
  me: ['me'] as const,
  company: (companyId: string) => ['companies', companyId] as const,
  agent: (companyId: string) => ['companies', companyId, 'agent'] as const,
  orders: ['orders'] as const,
  ordersByFilter: (filter: OrderListFilter) => ['orders', filter] as const,
  menu: ['menu'] as const,
  instances: ['instances'] as const,
  gateways: ['gateways'] as const,
  gatewayList: ['gateways', 'list'] as const,
  gatewayAssignments: ['gateways', 'assignments'] as const,
  dashboard: ['dashboard'] as const,
  dashboardPart: (part: string, ...args: string[]) => ['dashboard', part, ...args] as const,
}
