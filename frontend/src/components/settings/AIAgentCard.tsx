'use client'

import { useState } from 'react'
import { Bot, Save } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { FieldError } from '@/components/settings/gateways/FieldError'
import type { CompanySettingsState } from '@/hooks/useCompanySettings'
import { useSettingsStore } from '@/stores/useSettingsStore'
import { AGENT_INSTRUCTIONS_MAX_LENGTH, type AgentSettings } from '@/types/company'

/** Ajustes de resposta do Agent da Company; o modelo vem do Gateway atribuído. */
export function AIAgentCard({ settings }: { settings: CompanySettingsState }) {
  const { agent, loading, error, saveAgent } = settings
  if (loading || !agent) {
    return (
      <div className="rounded-2xl border border-border-color bg-card p-7 text-sm text-text-gray" role={error ? 'alert' : 'status'}>
        {error ?? (loading ? 'Carregando o Agent...' : 'Esta empresa ainda não tem um Agent cadastrado.')}
      </div>
    )
  }
  return <AgentForm agent={agent} saveAgent={saveAgent} />
}

const DEFAULT_TEMPERATURE = 0.7

function AgentForm({ agent, saveAgent }: { agent: AgentSettings; saveAgent: CompanySettingsState['saveAgent'] }) {
  const setActiveTab = useSettingsStore((state) => state.setActiveTab)
  const [useGatewayTemperature, setUseGatewayTemperature] = useState(agent.temperature === null)
  const [temperature, setTemperature] = useState(agent.temperature ?? DEFAULT_TEMPERATURE)
  const [maxTokens, setMaxTokens] = useState(String(agent.max_tokens))
  const [instructions, setInstructions] = useState(agent.system_prompt ?? '')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)
    setSaved(false)
    const result = await saveAgent({
      temperature: useGatewayTemperature ? null : temperature,
      max_tokens: /^\d+$/.test(maxTokens.trim()) ? Number(maxTokens) : NaN,
      system_prompt: instructions,
    })
    setErrors(result.ok ? {} : result.fieldErrors)
    if (result.ok) {
      setUseGatewayTemperature(result.value.temperature === null)
      setTemperature(result.value.temperature ?? DEFAULT_TEMPERATURE)
      setMaxTokens(String(result.value.max_tokens))
      setInstructions(result.value.system_prompt ?? '')
    }
    setSaved(result.ok)
    setIsSaving(false)
  }

  return (
    <div className="rounded-2xl border border-border-color bg-card p-7">
      <div className="mb-6 flex items-center gap-4">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-500/10">
          <Bot className="h-5 w-5 text-indigo-500" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-text-light">Comportamento do Agent</h3>
          <p className="text-sm text-text-gray">Ajustes de resposta; o modelo vem do Gateway atribuído</p>
        </div>
      </div>

      <div className="space-y-4">
        <p className="rounded-xl border border-border-color bg-input px-4 py-3 text-sm text-text-gray">
          O modelo e o provider são os do Gateway atribuído ao Agent.{' '}
          <button
            type="button"
            onClick={() => setActiveTab('gateways')}
            className="font-medium text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Abrir aba Gateways
          </button>
        </p>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="agent-temperature" className="text-sm font-medium text-text-light">Temperatura</label>
            <span className="text-sm font-semibold text-primary">{useGatewayTemperature ? 'Padrão do Gateway' : temperature}</span>
          </div>
          <div className="flex h-11 items-center rounded-xl border border-border-color bg-input px-4">
            <input
              id="agent-temperature"
              type="range"
              min="0"
              max="1"
              step="0.1"
              disabled={useGatewayTemperature}
              aria-invalid={Boolean(errors.temperature)}
              aria-describedby={errors.temperature ? 'agent-temperature-error' : undefined}
              value={temperature}
              onChange={(e) => {
                setTemperature(parseFloat(e.target.value))
                setSaved(false)
              }}
              className="w-full accent-primary disabled:opacity-40"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-text-gray">
            <input
              type="checkbox"
              checked={useGatewayTemperature}
              onChange={(e) => {
                setUseGatewayTemperature(e.target.checked)
                setSaved(false)
              }}
            />
            Usar a temperatura padrão do Gateway
          </label>
          <FieldError id="agent-temperature-error" message={errors.temperature} />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="agent-max-tokens" className="text-sm font-medium text-text-light">Máximo de tokens por resposta</label>
          <Input
            id="agent-max-tokens"
            type="number"
            value={maxTokens}
            aria-invalid={Boolean(errors.max_tokens)}
            aria-describedby={errors.max_tokens ? 'agent-max-tokens-error' : undefined}
            onChange={(e) => {
              setMaxTokens(e.target.value)
              setSaved(false)
            }}
            placeholder="1000"
          />
          <FieldError id="agent-max-tokens-error" message={errors.max_tokens} />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="agent-instructions" className="text-sm font-medium text-text-light">Instruções do atendente</label>
            <span
              id="agent-instructions-count"
              className={instructions.length > AGENT_INSTRUCTIONS_MAX_LENGTH ? 'text-sm font-semibold text-red-300' : 'text-sm text-text-gray'}
            >
              {instructions.length}/{AGENT_INSTRUCTIONS_MAX_LENGTH}
            </span>
          </div>
          <textarea
            id="agent-instructions"
            rows={5}
            value={instructions}
            aria-invalid={Boolean(errors.system_prompt) || instructions.length > AGENT_INSTRUCTIONS_MAX_LENGTH}
            aria-describedby={`agent-instructions-hint agent-instructions-count${errors.system_prompt ? ' agent-instructions-error' : ''}`}
            onChange={(e) => {
              setInstructions(e.target.value)
              setSaved(false)
            }}
            placeholder="Ex.: Seu nome é Ana. Não fazemos entrega aos domingos. Promoção de terça: pizza grande com 20% off."
            className="flex min-h-28 w-full rounded-md border border-border-color bg-dark px-4 py-3 text-sm text-text-light placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          <p id="agent-instructions-hint" className="text-xs text-text-gray">
            Nome, tom e avisos fixos. Não substituem as regras do sistema: dados só das ferramentas, resumo antes de fechar o pedido e transferência para uma pessoa. Vazio remove as instruções.
          </p>
          <FieldError id="agent-instructions-error" message={errors.system_prompt} />
        </div>
      </div>

      <div className="mt-6 flex items-center justify-end gap-4">
        {errors._form && (
          <p role="alert" className="text-sm text-red-300">
            {errors._form}
          </p>
        )}
        {saved && (
          <p role="status" className="text-sm text-success">
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
