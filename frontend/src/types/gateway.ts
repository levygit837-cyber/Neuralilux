export type ReasoningEffort = 'low' | 'medium' | 'high'
export type AgentType = 'default' | 'whatsapp_agent'

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
