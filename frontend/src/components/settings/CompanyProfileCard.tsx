'use client'

import { useState } from 'react'
import { Building2, Save } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import type { CompanySettingsState } from '@/hooks/useCompanySettings'
import { Field } from './company/Field'
import { HoursEditor } from './company/HoursEditor'
import type { Company } from '@/types/company'
import { toDraft, toPayload, type CompanyDraft } from './company/drafts'

type TextField = Exclude<keyof CompanyDraft, 'hours'>

export function CompanyProfileCard({ settings }: { settings: CompanySettingsState }) {
  const { company, loading, error, saveCompany } = settings
  if (loading || !company) {
    return (
      <div className="rounded-2xl border border-brand-border bg-brand-card p-7 text-sm text-content-gray" role={error ? 'alert' : 'status'}>
        {error ?? 'Carregando dados da empresa...'}
      </div>
    )
  }
  return <CompanyForm company={company} saveCompany={saveCompany} />
}

function CompanyForm({ company, saveCompany }: { company: Company; saveCompany: CompanySettingsState['saveCompany'] }) {
  const [draft, setDraft] = useState<CompanyDraft>(() => toDraft(company))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const change = (field: TextField, value: string) => {
    setDraft((prev) => ({ ...prev, [field]: value }))
    setSaved(false)
    setErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([key]) => key !== field)))
  }

  const text = (field: TextField, label: string, props: { placeholder?: string; hint?: string; type?: string } = {}) => (
    <Field id={`company-${field}`} label={label} error={errors[field]} hint={props.hint}>
      <Input
        id={`company-${field}`}
        type={props.type}
        value={draft[field]}
        placeholder={props.placeholder}
        aria-invalid={Boolean(errors[field])}
        aria-describedby={errors[field] ? `company-${field}-error` : undefined}
        onChange={(e) => change(field, e.target.value)}
      />
    </Field>
  )

  const handleSave = async () => {
    setIsSaving(true)
    setSaved(false)
    const result = await saveCompany(toPayload(draft))
    setErrors(result.ok ? {} : result.fieldErrors)
    // O formulário passa a mostrar o que o backend gravou (valores normalizados, campos limpos).
    if (result.ok) setDraft(toDraft(result.value))
    setSaved(result.ok)
    setIsSaving(false)
  }

  return (
    <div className="rounded-2xl border border-brand-border bg-brand-card p-7">
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
          <Building2 className="h-5 w-5 text-primary-light" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-content-light">Informações da Empresa</h3>
          <p className="text-sm text-content-gray">O Agent usa estes dados para atender seus clientes</p>
        </div>
      </div>

      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          {text('name', 'Nome da empresa')}
          {text('email', 'Email de contato', { placeholder: 'contato@empresa.com', type: 'email' })}
        </div>
        <div className="grid grid-cols-2 gap-4">
          {text('phone', 'Telefone', { placeholder: '(85) 99999-0000' })}
          {text('pix_key', 'Chave Pix', { hint: 'E-mail, CPF, CNPJ, celular com +55 ou chave aleatória. Vazio: a empresa não aceita Pix.' })}
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">{text('address_street', 'Rua')}</div>
          {text('address_number', 'Número')}
        </div>
        <div className="grid grid-cols-3 gap-4">
          {text('address_complement', 'Complemento')}
          {text('address_neighborhood', 'Bairro')}
          {text('address_zip', 'CEP')}
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">{text('address_city', 'Cidade')}</div>
          {text('address_state', 'UF', { placeholder: 'CE' })}
        </div>

        <div className="border-t border-brand-border" />

        <HoursEditor
          hours={draft.hours}
          error={errors.business_hours}
          onChange={(hours) => {
            setDraft({ ...draft, hours })
            setSaved(false)
            setErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([key]) => key !== 'business_hours')))
          }}
        />
        {text('timezone', 'Fuso horário', { placeholder: 'America/Fortaleza', hint: 'Nome IANA. Os horários acima valem neste fuso.' })}

        <div className="grid grid-cols-3 gap-4">
          {text('minimum_order', 'Pedido mínimo (R$)', { placeholder: '30,00', hint: 'Soma dos itens, sem a entrega. Vazio: sem mínimo.' })}
          {text('session_timeout_minutes', 'Limite da Session (min)', { type: 'number', hint: 'Sem mensagens por este tempo, começa um novo atendimento.' })}
          {text('handoff_timeout_hours', 'Timeout do Handoff (h)', { type: 'number', hint: 'Sem atendente agir por este tempo, o Agent volta a responder.' })}
        </div>
      </div>

      <div className="mt-6 flex items-center justify-end gap-4">
        {errors._form && (
          <p role="alert" className="text-sm text-status-error">
            {errors._form}
          </p>
        )}
        {saved && (
          <p role="status" className="text-sm text-status-success">
            Alterações salvas
          </p>
        )}
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="mr-2 h-4 w-4" />
          {isSaving ? 'Salvando...' : 'Salvar alterações'}
        </Button>
      </div>
    </div>
  )
}
