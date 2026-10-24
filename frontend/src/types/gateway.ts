export type ReasoningEffort = 'low' | 'medium' | 'high'
export type AgentType = 'default' | 'whatsapp_agent'

export const AGENT_LABELS: Record<AgentType, { title: string; hint: string }> = {
  default: { title: 'Padrão', hint: 'Usado quando o agente não tem modelo próprio' },
  whatsapp_agent: { title: 'Agente do WhatsApp', hint: 'Atende os clientes nas conversas' },
}
export const AGENT_TYPES = Object.keys(AGENT_LABELS) as AgentType[]

export interface GatewayModel {
  id: string
  gateway_id: string
  name: string
  model_id: string
  reasoning_effort: ReasoningEffort | null
  max_tokens: number | null
  temperature: number | null
  supports_tools: boolean
  is_active: boolean
}

export interface Gateway {
  id: string
  name: string
  base_url: string
  has_api_key: boolean
  timeout_seconds: number
  is_active: boolean
  models: GatewayModel[]
}

export interface GatewayAssignment {
  agent_type: AgentType
  gateway_model_id: string
  gateway_id: string
  gateway_name: string
  model_name: string
  model_id: string
}

/** Leitura enxuta para qualquer usuário logado (`GET /gateways/active-models`): sem URL, ids nem chave. */
export interface ActiveModel {
  agent_type: AgentType
  gateway_name: string
  model_name: string
}

export interface GatewayInput {
  name: string
  base_url: string
  /** Em edição: undefined mantém, '' remove, texto substitui. */
  api_key?: string
  timeout_seconds: number
  is_active: boolean
}

export interface GatewayModelInput {
  name: string
  model_id: string
  reasoning_effort: ReasoningEffort | null
  max_tokens: number | null
  temperature: number | null
  supports_tools: boolean
  is_active: boolean
}

export interface ProbeResult {
  ok: boolean
  latency_ms?: number
  content?: string
  thinking?: boolean
  error?: string
}

/** Timeout padrão de um Gateway novo; o backend usa o mesmo valor (60 s). */
export const DEFAULT_GATEWAY_TIMEOUT_SECONDS = 60

/** Origem (esquema + host + porta) de uma URL, normalizada como o backend. `null` se não for uma URL. */
export function originOf(url: string): string | null {
  try {
    return new URL(url.trim()).origin
  } catch {
    return null
  }
}

/**
 * `true` quando `next` aponta para outra origem que `previous`. A chave salva só pode seguir para a mesma origem;
 * o backend exige `api_key` de novo (ou `''` para apagar) quando a origem muda. URL incompleta não conta.
 */
export function originChanged(next: string, previous?: string): boolean {
  if (!previous) return false
  const to = originOf(next)
  const from = originOf(previous)
  return to !== null && from !== null && to !== from
}
