import { originChanged, type GatewayModelInput } from '@/types/gateway'

export interface GatewayDraft {
  id?: string
  name: string
  base_url: string
  /** URL salva ao abrir a edição; base para detectar a troca de origem. */
  originalBaseUrl?: string
  api_key: string
  hasStoredKey: boolean
  clearKey: boolean
  timeout_seconds: number
  is_active: boolean
}

export interface ModelDraft extends GatewayModelInput {
  id?: string
  gateway_id: string
}

/** Edição que mudou a origem sem decisão explícita sobre a chave (informar uma nova ou marcar que não há chave). */
export function needsKeyForNewOrigin(draft: GatewayDraft): boolean {
  return Boolean(draft.id) && !draft.api_key && !draft.clearKey && originChanged(draft.base_url, draft.originalBaseUrl)
}
