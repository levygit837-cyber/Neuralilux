'use client'

import { useState } from 'react'
import { Palette, Globe, Clock, Save } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useSettingsStore } from '@/stores/useSettingsStore'

export function ThemeAppearanceCard() {
  const { settings, updateTheme } = useSettingsStore()
  const [formData, setFormData] = useState(settings.theme)
  const [isSaving, setIsSaving] = useState(false)

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      updateTheme(formData)
      // TODO: Integrate with backend
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-2xl border border-border-color bg-card p-7">
      {/* Card Header */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-500/10">
          <Palette className="h-5 w-5 text-sky-500" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-light">Tema e Aparência</h3>
          <p className="text-sm text-text-gray">Personalize a aparência do painel</p>
        </div>
      </div>

      {/* Theme Selector */}
      <div className="mb-6 space-y-2">
        <label className="text-sm font-medium text-text-light">Tema</label>
        <div className="grid grid-cols-2 gap-4">
          {/* Dark Theme */}
          <button
            onClick={() => handleChange('theme', 'dark')}
            className={`flex items-center gap-3 rounded-xl border p-4 transition-colors ${
              formData.theme === 'dark'
                ? 'border-primary bg-primary/5'
                : 'border-border-color bg-input hover:border-border'
            }`}
          >
            <div className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
              formData.theme === 'dark' ? 'border-primary' : 'border-border-color'
            }`}>
              {formData.theme === 'dark' && (
                <div className="h-2.5 w-2.5 rounded-full bg-primary" />
              )}
            </div>
            <div className="text-left">
              <p className={`text-sm font-medium ${
                formData.theme === 'dark' ? 'text-text-light' : 'text-text-gray'
              }`}>
                Escuro
              </p>
              <p className="text-xs text-text-gray">Tema padrão</p>
            </div>
          </button>

          {/* Light Theme */}
          <button
            onClick={() => handleChange('theme', 'light')}
            className={`flex items-center gap-3 rounded-xl border p-4 transition-colors ${
              formData.theme === 'light'
                ? 'border-primary bg-primary/5'
                : 'border-border-color bg-input hover:border-border'
            }`}
          >
            <div className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
              formData.theme === 'light' ? 'border-primary' : 'border-border-color'
            }`}>
              {formData.theme === 'light' && (
                <div className="h-2.5 w-2.5 rounded-full bg-primary" />
              )}
            </div>
            <div className="text-left">
              <p className={`text-sm font-medium ${
                formData.theme === 'light' ? 'text-text-light' : 'text-text-gray'
              }`}>
                Claro
              </p>
              <p className="text-xs text-text-gray">Em breve</p>
            </div>
          </button>
        </div>
      </div>

      {/* Row: Idioma + Fuso Horário */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <Globe className="h-3.5 w-3.5 text-text-gray" />
            <label className="text-sm font-medium text-text-light">Idioma</label>
          </div>
          <Input
            value={formData.language}
            onChange={(e) => handleChange('language', e.target.value)}
            placeholder="Português (BR)"
          />
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-text-gray" />
            <label className="text-sm font-medium text-text-light">Fuso horário</label>
          </div>
          <Input
            value={formData.timezone}
            onChange={(e) => handleChange('timezone', e.target.value)}
            placeholder="America/Sao_Paulo (GMT-3)"
          />
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