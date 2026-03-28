'use client'

import { useState } from 'react'
import { Building2, Mail, Phone, Save } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useSettingsStore } from '@/stores/useSettingsStore'

export function CompanyProfileCard() {
  const { settings, updateCompany } = useSettingsStore()
  const [formData, setFormData] = useState(settings.company)
  const [isSaving, setIsSaving] = useState(false)

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      updateCompany(formData)
      // TODO: Integrate with backend
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-2xl border border-border-color bg-card p-7">
      {/* Card Header */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
          <Building2 className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-light">Informações da Empresa</h3>
          <p className="text-sm text-text-gray">Configure os dados da sua empresa</p>
        </div>
      </div>

      {/* Form */}
      <div className="space-y-4">
        {/* Row: Nome + Tipo */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Nome da empresa</label>
            <Input
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="Nome da empresa"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Tipo de negócio</label>
            <Input
              value={formData.businessType}
              onChange={(e) => handleChange('businessType', e.target.value)}
              placeholder="Tipo de negócio"
            />
          </div>
        </div>

        {/* Row: Email + Telefone */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Email de contato</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-gray" />
              <Input
                value={formData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                placeholder="contato@empresa.com"
                className="pl-10"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Telefone</label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-gray" />
              <Input
                value={formData.phone}
                onChange={(e) => handleChange('phone', e.target.value)}
                placeholder="+55 11 99999-0000"
                className="pl-10"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="mt-6 flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="mr-2 h-4 w-4" />
          {isSaving ? 'Salvando...' : 'Salvar alterações'}
        </Button>
      </div>
    </div>
  )
}