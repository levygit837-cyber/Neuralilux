export const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const
export type DayKey = (typeof DAY_KEYS)[number]

export const DAY_LABELS: Record<DayKey, string> = {
  mon: 'Segunda',
  tue: 'Terça',
  wed: 'Quarta',
  thu: 'Quinta',
  fri: 'Sexta',
  sat: 'Sábado',
  sun: 'Domingo',
}

export type Interval = [string, string]
export type BusinessHours = Partial<Record<DayKey, Interval[]>>

/** Company como o backend devolve (`CompanyResponse`). */
export interface Company {
  id: string
  name: string
  description: string | null
  address_street: string | null
  address_number: string | null
  address_complement: string | null
  address_neighborhood: string | null
  address_city: string | null
  address_state: string | null
  address_zip: string | null
  phone: string | null
  email: string | null
  pix_key: string | null
  minimum_order: number | null
  business_hours: BusinessHours | null
  timezone: string
  session_timeout_minutes: number
  handoff_timeout_hours: number
}

/** Corpo do PUT: só os campos que o painel edita. */
export type CompanyUpdate = Partial<Omit<Company, 'id' | 'minimum_order'>> & {
  // O backend aceita Decimal em texto ("30.50"), sem perder centavos em float.
  minimum_order?: number | string | null
}

/** Ajustes de resposta do Agent da Company (`AgentSettings`). */
export interface AgentSettings {
  temperature: number | null
  max_tokens: number
  /** Instruções da Company para o Agent (nome, tom, avisos fixos); `null` quando não há. */
  system_prompt: string | null
}

/** Mesmo limite do backend (`AGENT_INSTRUCTIONS_MAX_LENGTH`); acima disso o `PUT` responde 422. */
export const AGENT_INSTRUCTIONS_MAX_LENGTH = 2000
