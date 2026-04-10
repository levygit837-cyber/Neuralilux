'use client'

import { useState } from 'react'
import { Bot, Save } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useSettingsStore } from '@/stores/useSettingsStore'

export function AIAgentCard() {
  const { settings, updateAIAgent } = useSettingsStore()
  const [formData, setFormData] = useState(settings.aiAgent)
  const [isSaving, setIsSaving] = useState(false)

  const handleChange = (field: string, value: string | number | boolean) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      updateAIAgent(formData)
      // TODO: Integrate with backend
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-2xl border border-border-color bg-card p-7">
      {/* Card Header */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-500/10">
          <Bot className="h-5 w-5 text-indigo-500" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-light">Modelo de IA</h3>
          <p className="text-sm text-text-gray">Escolha e configure o modelo de inteligência artificial</p>
        </div>
      </div>

      {/* Form */}
      <div className="space-y-4">
        {/* Row: Modelo + Temperatura */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Modelo</label>
            <Input
              value={formData.model}
              onChange={(e) => handleChange('model', e.target.value)}
              placeholder="GPT-4o"
            />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-text-light">Temperatura</label>
              <span className="text-sm font-semibold text-primary">{formData.temperature}</span>
            </div>
            <div className="flex h-11 items-center rounded-xl border border-border-color bg-input px-4">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={formData.temperature}
                onChange={(e) => handleChange('temperature', parseFloat(e.target.value))}
                className="w-full accent-primary"
              />
            </div>
          </div>
        </div>

        {/* Row: Tokens + Timeout */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Máximo de tokens</label>
            <Input
              type="number"
              value={formData.maxTokens}
              onChange={(e) => handleChange('maxTokens', parseInt(e.target.value))}
              placeholder="4096"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Timeout (s)</label>
            <Input
              type="number"
              value={formData.timeout}
              onChange={(e) => handleChange('timeout', parseInt(e.target.value))}
              placeholder="30"
            />
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-border-color" />

        {/* Toggles */}
        <div className="space-y-1">
          {/* Memória ativa */}
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium text-text-light">Memória ativa</p>
              <p className="text-xs text-text-gray">Mantém contexto entre mensagens</p>
            </div>
            <button
              onClick={() => handleChange('memoryEnabled', !formData.memoryEnabled)}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                formData.memoryEnabled ? 'bg-success' : 'bg-border-color'
              }`}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                  formData.memoryEnabled ? 'left-[22px]' : 'left-0.5'
                }`}
              />
            </button>
          </div>

          {/* Auto-resposta */}
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium text-text-light">Auto-resposta</p>
              <p className="text-xs text-text-gray">Responde automaticamente às mensagens</p>
            </div>
            <button
              onClick={() => handleChange('autoReplyEnabled', !formData.autoReplyEnabled)}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                formData.autoReplyEnabled ? 'bg-success' : 'bg-border-color'
              }`}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                  formData.autoReplyEnabled ? 'left-[22px]' : 'left-0.5'
                }`}
              />
            </button>
          </div>

          {/* Modo debug */}
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium text-text-light">Modo debug</p>
              <p className="text-xs text-text-gray">Exibe logs detalhados de processamento</p>
            </div>
            <button
              onClick={() => handleChange('debugMode', !formData.debugMode)}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                formData.debugMode ? 'bg-success' : 'bg-border-color'
              }`}
            >
              <span
                className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
                  formData.debugMode ? 'left-[22px]' : 'left-0.5'
                }`}
              />
            </button>
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