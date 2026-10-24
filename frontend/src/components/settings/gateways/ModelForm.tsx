import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import type { ReasoningEffort } from '@/types/gateway'
import { EFFORTS, fieldLabel, selectClass } from './constants'
import type { ModelDraft } from './drafts'
import { FieldError } from './FieldError'

interface ModelFormProps {
  draft: ModelDraft
  errors: Record<string, string>
  saving: boolean
  remoteModels: Record<string, string[]>
  onPatch: (patch: Partial<ModelDraft>) => void
  onSubmit: () => void
  onCancel: () => void
}

export function ModelForm({
  draft: modelDraft,
  errors: modelErrors,
  saving,
  remoteModels,
  onPatch: patchModel,
  onSubmit,
  onCancel,
}: ModelFormProps) {
  return (
    <form
      className="space-y-4 rounded-2xl border border-primary/50 bg-brand-card p-6"
      aria-label={modelDraft.id ? 'Editar modelo' : 'Novo modelo'}
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <h3 className="text-base font-semibold text-content-light">
        {modelDraft.id ? 'Editar modelo' : 'Novo modelo'}
      </h3>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label className={fieldLabel} htmlFor="gm-name">Nome na lista</label>
          <Input id="gm-name" required value={modelDraft.name} placeholder="Sonnet 5.5 (low)"
            aria-invalid={Boolean(modelErrors.name)}
            aria-describedby={modelErrors.name ? 'gm-name-error' : undefined}
            onChange={(e) => patchModel({ name: e.target.value })} />
          <FieldError id="gm-name-error" message={modelErrors.name} />
        </div>
        <div>
          <label className={fieldLabel} htmlFor="gm-id">ID do modelo no gateway</label>
          <Input id="gm-id" required list="gm-remote" value={modelDraft.model_id} placeholder="claude-sonnet-5.5"
            aria-invalid={Boolean(modelErrors.model_id)}
            aria-describedby={modelErrors.model_id ? 'gm-id-error' : undefined}
            onChange={(e) => patchModel({ model_id: e.target.value })} />
          <datalist id="gm-remote">
            {(remoteModels[modelDraft.gateway_id] ?? []).map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </datalist>
          <FieldError id="gm-id-error" message={modelErrors.model_id} />
        </div>
        <div>
          <label className={fieldLabel} htmlFor="gm-effort">Esforço de raciocínio</label>
          <select id="gm-effort" className={selectClass} value={modelDraft.reasoning_effort ?? ''}
            aria-invalid={Boolean(modelErrors.reasoning_effort)}
            aria-describedby={modelErrors.reasoning_effort ? 'gm-effort-error' : undefined}
            onChange={(e) => patchModel({ reasoning_effort: (e.target.value || null) as ReasoningEffort | null })}>
            {EFFORTS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <FieldError id="gm-effort-error" message={modelErrors.reasoning_effort} />
        </div>
        <div>
          <label className={fieldLabel} htmlFor="gm-max">Máx. de tokens (vazio = padrão)</label>
          <Input id="gm-max" type="number" min={1} value={modelDraft.max_tokens ?? ''}
            aria-invalid={Boolean(modelErrors.max_tokens)}
            aria-describedby={modelErrors.max_tokens ? 'gm-max-error' : undefined}
            onChange={(e) =>
              patchModel({ max_tokens: e.target.value.trim() === '' ? null : Number(e.target.value) })
            } />
          <FieldError id="gm-max-error" message={modelErrors.max_tokens} />
        </div>
        <div>
          <label className={fieldLabel} htmlFor="gm-temp">Temperatura (vazio = padrão)</label>
          <Input id="gm-temp" type="number" min={0} max={2} step={0.1} value={modelDraft.temperature ?? ''}
            aria-invalid={Boolean(modelErrors.temperature)}
            aria-describedby={modelErrors.temperature ? 'gm-temp-error' : undefined}
            onChange={(e) =>
              patchModel({ temperature: e.target.value.trim() === '' ? null : Number(e.target.value) })
            } />
          <FieldError id="gm-temp-error" message={modelErrors.temperature} />
        </div>
        <div className="flex flex-col justify-end gap-2 pb-3 text-sm text-content-light">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={modelDraft.supports_tools}
              onChange={(e) => patchModel({ supports_tools: e.target.checked })} />
            Aceita ferramentas (function calling)
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={modelDraft.is_active}
              onChange={(e) => patchModel({ is_active: e.target.checked })} />
            Ativo
          </label>
        </div>
      </div>
      <div className="flex gap-3">
        <Button type="submit" disabled={saving}>Salvar</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>Cancelar</Button>
      </div>
    </form>
  )
}
