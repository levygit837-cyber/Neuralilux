'use client'

import { useState } from 'react'
import { Cpu, Save, Cloud, Monitor } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useSettingsStore } from '@/stores/useSettingsStore'
import type { InferenceProvider, LocalModel } from '@/types/settings'
import { API_BASE_URL } from '@/lib/constants'

export function InferenceProviderCard() {
  const { settings, updateAIAgent } = useSettingsStore()
  const defaultInference = {
    provider: 'gemini' as const,
    localModel: 'nemotron' as const,
    geminiApiKey: '',
    geminiModel: 'gemini-3.1-flash-preview',
    lmStudioUrl: 'http://localhost:1234',
  }
  const [formData, setFormData] = useState(settings.aiAgent.inference || defaultInference)
  const [isSaving, setIsSaving] = useState(false)

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleProviderChange = (provider: InferenceProvider) => {
    setFormData((prev) => ({ ...prev, provider }))
  }

  const handleLocalModelChange = (localModel: LocalModel) => {
    setFormData((prev) => ({ ...prev, localModel }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      // Salvar no store local
      updateAIAgent({ inference: formData })
      
      // Enviar para o backend
      const response = await fetch(`${API_BASE_URL}/api/v1/settings/inference`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          provider: formData.provider,
          local_model: formData.localModel,
          gemini_api_key: formData.geminiApiKey,
          gemini_model: formData.geminiModel,
          lm_studio_url: formData.lmStudioUrl,
        }),
      })
      
      if (!response.ok) {
        throw new Error('Falha ao salvar configuração')
      }
      
      const result = await response.json()
      console.log('Configuração salva:', result)
    } catch (error) {
      console.error('Erro ao salvar:', error)
      alert('Erro ao salvar configuração. Verifique se o backend está rodando.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-2xl border border-border-color bg-card p-7">
      {/* Card Header */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-purple-500/10">
          <Cpu className="h-5 w-5 text-purple-500" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-light">Provedor de Inferência</h3>
          <p className="text-sm text-text-gray">Escolha entre modelo local ou na nuvem</p>
        </div>
      </div>

      {/* Provider Selection */}
      <div className="mb-6">
        <label className="mb-3 block text-sm font-medium text-text-light">Provedor</label>
        <div className="grid grid-cols-2 gap-3">
          {/* Local Option */}
          <button
            onClick={() => handleProviderChange('lm_studio')}
            className={`flex items-center gap-3 rounded-xl border p-4 transition-all ${
              formData.provider === 'lm_studio'
                ? 'border-primary bg-primary/10'
                : 'border-border-color bg-input hover:border-primary/50'
            }`}
          >
            <Monitor className={`h-5 w-5 ${formData.provider === 'lm_studio' ? 'text-primary' : 'text-text-gray'}`} />
            <div className="text-left">
              <p className={`text-sm font-medium ${formData.provider === 'lm_studio' ? 'text-primary' : 'text-text-light'}`}>
                Modelo Local
              </p>
              <p className="text-xs text-text-gray">LM Studio (localhost)</p>
            </div>
          </button>

          {/* Cloud Option */}
          <button
            onClick={() => handleProviderChange('gemini')}
            className={`flex items-center gap-3 rounded-xl border p-4 transition-all ${
              formData.provider === 'gemini'
                ? 'border-primary bg-primary/10'
                : 'border-border-color bg-input hover:border-primary/50'
            }`}
          >
            <Cloud className={`h-5 w-5 ${formData.provider === 'gemini' ? 'text-primary' : 'text-text-gray'}`} />
            <div className="text-left">
              <p className={`text-sm font-medium ${formData.provider === 'gemini' ? 'text-primary' : 'text-text-light'}`}>
                Google Gemini
              </p>
              <p className="text-xs text-text-gray">API na nuvem</p>
            </div>
          </button>
        </div>
      </div>

      {/* Local Model Selection (when LM Studio is selected) */}
      {formData.provider === 'lm_studio' && (
        <div className="mb-6 rounded-xl border border-border-color bg-input p-4">
          <label className="mb-3 block text-sm font-medium text-text-light">Modelo Local</label>
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => handleLocalModelChange('nemotron')}
              className={`rounded-lg border p-3 text-left transition-all ${
                formData.localModel === 'nemotron'
                  ? 'border-primary bg-primary/10'
                  : 'border-border-color bg-card hover:border-primary/50'
              }`}
            >
              <p className={`text-sm font-medium ${formData.localModel === 'nemotron' ? 'text-primary' : 'text-text-light'}`}>
                Nemotron
              </p>
              <p className="text-xs text-text-gray">NVIDIA Nemotron-3-nano-4b</p>
            </button>
            <button
              onClick={() => handleLocalModelChange('qwen')}
              className={`rounded-lg border p-3 text-left transition-all ${
                formData.localModel === 'qwen'
                  ? 'border-primary bg-primary/10'
                  : 'border-border-color bg-card hover:border-primary/50'
              }`}
            >
              <p className={`text-sm font-medium ${formData.localModel === 'qwen' ? 'text-primary' : 'text-text-light'}`}>
                Qwen 3.5
              </p>
              <p className="text-xs text-text-gray">qwen3.5-4b-claude-4.6-opus-reasoning-distilled-v2</p>
            </button>
          </div>

          {/* LM Studio URL */}
          <div className="mt-4 space-y-1.5">
            <label className="text-sm font-medium text-text-light">URL do LM Studio</label>
            <Input
              value={formData.lmStudioUrl}
              onChange={(e) => handleChange('lmStudioUrl', e.target.value)}
              placeholder="http://localhost:1234"
            />
          </div>
        </div>
      )}

      {/* Gemini Configuration (when Gemini is selected) */}
      {formData.provider === 'gemini' && (
        <div className="mb-6 rounded-xl border border-border-color bg-input p-4">
          <label className="mb-3 block text-sm font-medium text-text-light">Configuração Gemini</label>
          
          {/* Gemini API Key */}
          <div className="mb-4 space-y-1.5">
            <label className="text-sm font-medium text-text-light">API Key</label>
            <Input
              type="password"
              value={formData.geminiApiKey}
              onChange={(e) => handleChange('geminiApiKey', e.target.value)}
              placeholder="AIzaSy..."
            />
          </div>

          {/* Gemini Model */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Modelo</label>
            <select
              value={formData.geminiModel}
              onChange={(e) => handleChange('geminiModel', e.target.value)}
              className="h-11 w-full rounded-xl border border-border-color bg-card px-4 text-sm text-text-light outline-none focus:border-primary"
            >
              <option value="gemini-3.1-flash-preview">gemini-3.1-flash-preview</option>
              <option value="gemini-3.1-flash-lite-preview">gemini-3.1-flash-lite-preview</option>
              <option value="gemini-pro">gemini-pro</option>
              <option value="gemini-pro-vision">gemini-pro-vision</option>
            </select>
          </div>
        </div>
      )}

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="mr-2 h-4 w-4" />
          {isSaving ? 'Salvando...' : 'Salvar alterações'}
        </Button>
      </div>
    </div>
  )
}