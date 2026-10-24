import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { DEFAULT_GATEWAY_TIMEOUT_SECONDS } from '@/types/gateway'
import { ORIGIN_KEY_MESSAGE, fieldLabel } from './constants'
import type { GatewayDraft } from './drafts'
import { FieldError } from './FieldError'

interface GatewayFormProps {
  draft: GatewayDraft
  errors: Record<string, string>
  saving: boolean
  keyRequired: boolean
  originMoved: boolean
  onPatch: (patch: Partial<GatewayDraft>) => void
  onSubmit: () => void
  onCancel: () => void
}

export function GatewayForm({
  draft: gatewayDraft,
  errors: gatewayErrors,
  saving,
  keyRequired,
  originMoved,
  onPatch: patchGateway,
  onSubmit,
  onCancel,
}: GatewayFormProps) {
  return (
    <form
      className="space-y-4 rounded-2xl border border-primary/50 bg-brand-card p-6"
      aria-label={gatewayDraft.id ? 'Editar gateway' : 'Novo gateway'}
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <h3 className="text-base font-semibold text-content-light">
        {gatewayDraft.id ? 'Editar gateway' : 'Novo gateway'}
      </h3>
      <div>
        <label className={fieldLabel} htmlFor="gw-name">Nome</label>
        <Input id="gw-name" required value={gatewayDraft.name} placeholder="Kiro-backend"
          aria-invalid={Boolean(gatewayErrors.name)}
          aria-describedby={gatewayErrors.name ? 'gw-name-error' : undefined}
          onChange={(e) => patchGateway({ name: e.target.value })} />
        <FieldError id="gw-name-error" message={gatewayErrors.name} />
      </div>
      <div>
        <label className={fieldLabel} htmlFor="gw-url">URL base (raiz, sem /v1)</label>
        <Input id="gw-url" required type="url" value={gatewayDraft.base_url} placeholder="http://localhost:5580"
          aria-invalid={Boolean(gatewayErrors.base_url)}
          aria-describedby={gatewayErrors.base_url ? 'gw-url-hint gw-url-error' : 'gw-url-hint'}
          onChange={(e) => patchGateway({ base_url: e.target.value })} />
        <p id="gw-url-hint" className="mt-1.5 text-xs text-content-muted">
          O cliente acrescenta /v1/messages a esta URL.
        </p>
        <FieldError id="gw-url-error" message={gatewayErrors.base_url} />
      </div>
      <div>
        <label className={fieldLabel} htmlFor="gw-key">Chave de API (opcional)</label>
        <Input id="gw-key" type="password" autoComplete="off" value={gatewayDraft.api_key}
          placeholder={gatewayDraft.hasStoredKey ? 'Salva. Digite para substituir' : 'sk-…'}
          aria-invalid={keyRequired || Boolean(gatewayErrors.api_key)}
          aria-describedby={
            keyRequired ? 'gw-key-reason' : gatewayErrors.api_key ? 'gw-key-error' : undefined
          }
          onChange={(e) => patchGateway({ api_key: e.target.value })} />
        {keyRequired && (
          <p id="gw-key-reason" role="alert" className="mt-1.5 text-xs text-status-error">
            {ORIGIN_KEY_MESSAGE}
          </p>
        )}
        <FieldError id="gw-key-error" message={gatewayErrors.api_key} />
        {(gatewayDraft.hasStoredKey || originMoved) && (
          <label className="mt-2 flex items-center gap-2 text-xs text-content-gray">
            <input type="checkbox" checked={gatewayDraft.clearKey}
              onChange={(e) => patchGateway({ clearKey: e.target.checked })} />
            {gatewayDraft.hasStoredKey ? 'Remover a chave salva' : 'Este endereço não usa chave de API'}
          </label>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label className={fieldLabel} htmlFor="gw-timeout">Timeout (segundos)</label>
          <Input id="gw-timeout" type="number" min={1} max={900} value={gatewayDraft.timeout_seconds}
            aria-invalid={Boolean(gatewayErrors.timeout_seconds)}
            aria-describedby={gatewayErrors.timeout_seconds ? 'gw-timeout-error' : undefined}
            onChange={(e) =>
              patchGateway({ timeout_seconds: Number(e.target.value) || DEFAULT_GATEWAY_TIMEOUT_SECONDS })
            } />
          <FieldError id="gw-timeout-error" message={gatewayErrors.timeout_seconds} />
        </div>
        <label className="flex items-center gap-2 self-end pb-3 text-sm text-content-light">
          <input type="checkbox" checked={gatewayDraft.is_active}
            onChange={(e) => patchGateway({ is_active: e.target.checked })} />
          Ativo
        </label>
      </div>
      <div className="flex gap-3">
        <Button
          type="submit"
          disabled={saving || keyRequired}
          aria-describedby={keyRequired ? 'gw-key-reason' : undefined}
        >
          Salvar
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>Cancelar</Button>
      </div>
    </form>
  )
}
