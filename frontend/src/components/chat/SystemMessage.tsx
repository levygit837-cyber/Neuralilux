import { Robot, Sparkle } from '@phosphor-icons/react'
import type { SystemMessageMetadata } from '@/types/chat'

interface SystemMessageProps {
  metadata: SystemMessageMetadata
}

export function SystemMessage({ metadata }: SystemMessageProps) {
  if (metadata.type === 'ai-takeover') {
    return (
      <div className="flex justify-center my-6">
        <div className="flex items-center gap-2 bg-primary/10 border border-primary/30 px-4 py-2 rounded-full">
          <Robot weight="fill" className="text-primary text-sm" />
          <span className="text-sm text-primary font-medium">
            {metadata.agentName || 'Agente IA'} assumiu a conversa
          </span>
          <Sparkle weight="fill" className="text-accent text-xs" />
        </div>
      </div>
    )
  }

  if (metadata.type === 'agent-handover') {
    return (
      <div className="flex justify-center my-6">
        <div className="flex items-center gap-2 bg-brand-card border border-brand-border px-4 py-2 rounded-full">
          <span className="text-sm text-content-muted">
            Conversa transferida para {metadata.agentName || 'atendente'}
          </span>
        </div>
      </div>
    )
  }

  if (metadata.type === 'system-notice') {
    return (
      <div className="flex justify-center my-6">
        <div className="flex items-center gap-2 bg-brand-card border border-brand-border px-4 py-2 rounded-full">
          <span className="text-sm text-content-muted">
            {metadata.message}
          </span>
        </div>
      </div>
    )
  }

  return null
}
