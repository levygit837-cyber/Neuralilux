import type { ReactNode } from 'react'
import { FieldError } from '@/components/settings/gateways/FieldError'

interface Props {
  id: string
  label: string
  error?: string
  hint?: string
  children: ReactNode
}

/** Rótulo, controle e erro de um campo; o erro vem do 422 do backend, por nome de campo. */
export function Field({ id, label, error, hint, children }: Props) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="text-sm font-medium text-text-light">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-text-gray">{hint}</p>}
      <FieldError id={`${id}-error`} message={error} />
    </div>
  )
}
