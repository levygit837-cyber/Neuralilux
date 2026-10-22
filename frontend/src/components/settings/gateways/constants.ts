import type { ReasoningEffort } from '@/types/gateway'

export const EFFORTS: { value: ReasoningEffort | ''; label: string }[] = [
  { value: '', label: 'Padrão do modelo' },
  { value: 'low', label: 'Baixo' },
  { value: 'medium', label: 'Médio' },
  { value: 'high', label: 'Alto' },
]

export const fieldLabel = 'mb-1.5 block text-xs font-medium text-text-gray'
export const selectClass =
  'h-12 w-full rounded-md border border-border-color bg-dark px-3 text-sm text-text-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'

export const READ_ONLY_MESSAGE = 'Somente administradores podem alterar Gateways'
export const ORIGIN_KEY_MESSAGE =
  'Você mudou a origem (esquema, host ou porta). A chave salva não é enviada para outro endereço: ' +
  'informe a chave deste endereço ou marque a opção abaixo.'
