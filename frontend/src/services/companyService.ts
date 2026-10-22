import { apiRequest, jsonBody } from '@/services/http'
import type { AgentSettings, Company, CompanyUpdate } from '@/types/company'

export const companyService = {
  get: (companyId: string) => apiRequest<Company>(`/companies/${companyId}`, {}, 'Falha ao carregar a empresa'),
  update: (companyId: string, body: CompanyUpdate) =>
    apiRequest<Company>(`/companies/${companyId}`, jsonBody('PUT', body), 'Falha ao salvar a empresa'),
  getAgent: (companyId: string) =>
    apiRequest<AgentSettings>(`/companies/${companyId}/agent`, {}, 'Falha ao carregar o Agent'),
  updateAgent: (companyId: string, body: Partial<AgentSettings>) =>
    apiRequest<AgentSettings>(`/companies/${companyId}/agent`, jsonBody('PUT', body), 'Falha ao salvar o Agent'),
}
