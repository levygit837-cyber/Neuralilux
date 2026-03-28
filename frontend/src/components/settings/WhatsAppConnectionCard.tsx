'use client'

import { useState } from 'react'
import { Smartphone, Save, Link, Eye, EyeOff, Wifi, WifiOff, Loader2, QrCode } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useSettingsStore } from '@/stores/useSettingsStore'

export function WhatsAppConnectionCard() {
  const { settings, updateWhatsApp } = useSettingsStore()
  const [formData, setFormData] = useState(settings.whatsapp)
  const [isSaving, setIsSaving] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [isTesting, setIsTesting] = useState(false)

  const handleChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      updateWhatsApp(formData)
      // TODO: Integrate with backend
    } finally {
      setIsSaving(false)
    }
  }

  const handleTestConnection = async () => {
    setIsTesting(true)
    try {
      // TODO: Integrate with backend
      await new Promise((resolve) => setTimeout(resolve, 2000))
    } finally {
      setIsTesting(false)
    }
  }

  const statusConfig = {
    connected: {
      label: 'Conectado',
      color: 'text-success',
      bgColor: 'bg-success/10',
      icon: Wifi,
    },
    disconnected: {
      label: 'Desconectado',
      color: 'text-error',
      bgColor: 'bg-error/10',
      icon: WifiOff,
    },
    connecting: {
      label: 'Conectando',
      color: 'text-warning',
      bgColor: 'bg-warning/10',
      icon: Loader2,
    },
  }

  const status = statusConfig[formData.status]
  const StatusIcon = status.icon

  return (
    <div className="rounded-2xl border border-border-color bg-card p-7">
      {/* Card Header */}
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10">
          <Smartphone className="h-5 w-5 text-emerald-500" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold text-text-light">Conexão WhatsApp</h3>
            <span className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${status.bgColor} ${status.color}`}>
              <StatusIcon className={`h-3.5 w-3.5 ${formData.status === 'connecting' ? 'animate-spin' : ''}`} />
              {status.label}
            </span>
          </div>
          <p className="text-sm text-text-gray">Gerencie a conexão com a Evolution API</p>
        </div>
      </div>

      {/* Form */}
      <div className="space-y-4">
        {/* URL da API */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-text-light">URL da API</label>
          <Input
            value={formData.apiUrl}
            onChange={(e) => handleChange('apiUrl', e.target.value)}
            placeholder="https://api.evolution.com"
          />
        </div>

        {/* Row: API Key + Nome da Instância */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">API Key</label>
            <div className="relative">
              <Input
                type={showApiKey ? 'text' : 'password'}
                value={formData.apiKey}
                onChange={(e) => handleChange('apiKey', e.target.value)}
                placeholder="••••••••••••"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-text-gray hover:text-text-light"
              >
                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-text-light">Nome da Instância</label>
            <Input
              value={formData.instanceName}
              onChange={(e) => handleChange('instanceName', e.target.value)}
              placeholder="neuralilux-prod"
            />
          </div>
        </div>
      </div>

      {/* Buttons */}
      <div className="mt-6 flex justify-end gap-3">
        <Button onClick={handleTestConnection} variant="secondary" disabled={isTesting}>
          <Link className={`mr-2 h-4 w-4 ${isTesting ? 'animate-spin' : ''}`} />
          {isTesting ? 'Testando...' : 'Testar Conexão'}
        </Button>
        <Button onClick={() => window.open('/qr', '_blank')} variant="secondary">
          <QrCode className="mr-2 h-4 w-4" />
          QR Code
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="mr-2 h-4 w-4" />
          {isSaving ? 'Salvando...' : 'Salvar'}
        </Button>
      </div>
    </div>
  )
}