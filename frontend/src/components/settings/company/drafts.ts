import { DAY_KEYS, type Company, type CompanyUpdate, type DayKey, type Interval } from '@/types/company'

/** Texto digitado no formulário; número só vira número no `toPayload`. */
export interface CompanyDraft {
  name: string
  email: string
  phone: string
  address_street: string
  address_number: string
  address_complement: string
  address_neighborhood: string
  address_city: string
  address_state: string
  address_zip: string
  pix_key: string
  minimum_order: string
  timezone: string
  session_timeout_minutes: string
  handoff_timeout_hours: string
  hours: Record<DayKey, Interval[]>
}

const text = (value: string | null) => value ?? ''

export function toDraft(company: Company): CompanyDraft {
  const hours = Object.fromEntries(
    DAY_KEYS.map((day) => [day, (company.business_hours?.[day] ?? []).map(([open, close]): Interval => [open, close])])
  ) as Record<DayKey, Interval[]>
  return {
    name: company.name,
    email: text(company.email),
    phone: text(company.phone),
    address_street: text(company.address_street),
    address_number: text(company.address_number),
    address_complement: text(company.address_complement),
    address_neighborhood: text(company.address_neighborhood),
    address_city: text(company.address_city),
    address_state: text(company.address_state),
    address_zip: text(company.address_zip),
    pix_key: text(company.pix_key),
    minimum_order: company.minimum_order === null ? '' : String(company.minimum_order),
    timezone: company.timezone,
    session_timeout_minutes: String(company.session_timeout_minutes),
    handoff_timeout_hours: String(company.handoff_timeout_hours),
    hours,
  }
}

/** Número inteiro digitado, ou NaN quando vazio/inválido (o backend recusa e o erro aparece no campo). */
const whole = (value: string) => (/^\d+$/.test(value.trim()) ? Number(value) : NaN)

export function toPayload(draft: CompanyDraft): CompanyUpdate {
  const { hours, minimum_order, session_timeout_minutes, handoff_timeout_hours, ...texts } = draft
  const openDays = DAY_KEYS.filter((day) => hours[day].length > 0)
  return {
    ...texts,
    // Vírgula decimal ("30,50") vale como ponto; vazio limpa o pedido mínimo.
    minimum_order: minimum_order.trim() === '' ? null : minimum_order.trim().replace(',', '.'),
    session_timeout_minutes: whole(session_timeout_minutes),
    handoff_timeout_hours: whole(handoff_timeout_hours),
    // Sem nenhum dia aberto, `null` limpa os horários (o Agent deixa de afirmar se está aberto).
    business_hours: openDays.length === 0 ? null : Object.fromEntries(DAY_KEYS.map((day) => [day, hours[day]])),
  }
}

/** O intervalo cruza a meia-noite quando o fim é menor ou igual ao início (ex.: 18:00 até 02:00). */
export const crossesMidnight = ([open, close]: Interval) => open !== '' && close !== '' && close <= open
