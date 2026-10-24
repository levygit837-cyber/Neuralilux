import { Avatar } from '@/components/ui/Avatar'
import { ArrowLeft, Phone, VideoCamera, MagnifyingGlass, DotsThreeVertical, Robot, Check, HandPalm, ArrowUUpLeft } from '@phosphor-icons/react'
import type { AgentListItem } from '@/types/chat'

interface ChatHeaderProps {
  name: string
  avatar?: string
  status?: string
  isOnline?: boolean
  humanHandoff?: boolean
  /** Alguém já assumiu o Handoff; sem isso o botão "Assumir" continua disponível. */
  handoffAssigned?: boolean
  onTakeControl?: () => void
  onReleaseControl?: () => void
  isHandoffPending?: boolean
  agentEnabled?: boolean | null
  agentName?: string | null
  availableAgents?: AgentListItem[]
  selectedAgentId?: string | null
  onSelectAgent?: (agentId: string | null) => void
  onToggleAgent?: () => void
  isAgentLoading?: boolean
  isAgentBindingLoading?: boolean
  /** Só abaixo de `lg`: volta da conversa para a lista. */
  onBack?: () => void
}

export function ChatHeader({
  name,
  avatar,
  status,
  isOnline,
  humanHandoff = false,
  handoffAssigned = false,
  onTakeControl,
  onReleaseControl,
  isHandoffPending = false,
  agentEnabled,
  agentName,
  availableAgents = [],
  selectedAgentId,
  onSelectAgent,
  onToggleAgent,
  isAgentLoading = false,
  isAgentBindingLoading = false,
  onBack,
}: ChatHeaderProps) {
  const isButtonDisabled = isAgentLoading || agentEnabled === null
  const isSelectorDisabled = isAgentLoading || isAgentBindingLoading
  const normalizedAgents =
    selectedAgentId &&
    agentName &&
    !availableAgents.some((agent) => agent.id === selectedAgentId)
      ? [{ id: selectedAgentId, name: agentName }, ...availableAgents]
      : availableAgents

  return (
    <header className="min-h-20 glass-header border-b border-brand-border/50 px-3 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-2 z-20">
      {/* Contact Info */}
      <div className="flex min-w-0 items-center gap-2 sm:gap-4 cursor-pointer group">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            aria-label="Voltar para as conversas"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-content-gray hover:bg-brand-hover hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary lg:hidden"
          >
            <ArrowLeft weight="regular" className="text-xl" aria-hidden="true" />
          </button>
        )}
        <div className="relative">
          <Avatar
            src={avatar}
            fallback={name.substring(0, 2).toUpperCase()}
            size="md"
          />
          {isOnline && (
            <div className="absolute bottom-0 right-0 w-3 h-3 bg-status-success border-[2.5px] border-[#1A1333] rounded-full" />
          )}
        </div>
        <div>
          <h2 className="font-semibold text-lg text-content-light leading-tight group-hover:text-primary transition-colors">{name}</h2>
          {status && (
            <p className="text-[13px] text-content-muted flex items-center gap-1.5">
              {isOnline && (
                <span className="w-1.5 h-1.5 rounded-full bg-status-success shadow-[0_0_5px_#10B981]" />
              )}
              {status}
            </p>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        {humanHandoff && (
          <span className="rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-semibold text-warning">
            Atendimento humano
          </span>
        )}
        {(!humanHandoff || !handoffAssigned) && (
          <button
            type="button"
            onClick={onTakeControl}
            disabled={isHandoffPending}
            className="flex items-center gap-2 rounded-lg border border-primary/40 bg-primary/10 px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <HandPalm weight="regular" className="text-lg" aria-hidden="true" />
            Assumir
          </button>
        )}
        {humanHandoff && (
          <button
            type="button"
            onClick={onReleaseControl}
            disabled={isHandoffPending}
            className="flex items-center gap-2 rounded-lg border border-brand-border/50 bg-brand-card/50 px-3 py-2 text-sm font-medium text-content-light transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ArrowUUpLeft weight="regular" className="text-lg" aria-hidden="true" />
            Devolver ao Agent
          </button>
        )}
        {/* Agent Toggle */}
        <div className="flex items-center gap-3 bg-brand-card/50 rounded-lg px-3 py-2 border border-brand-border/50">
          <Robot weight="regular" className="text-lg text-content-muted" />
          <button
            onClick={onToggleAgent}
            disabled={isButtonDisabled}
            className={`relative w-11 h-6 rounded-full transition-colors duration-200 ${
              agentEnabled ? 'bg-primary' : 'bg-brand-border'
            } ${isButtonDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
          >
            <span
              className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform duration-200 ${
                agentEnabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
          {agentEnabled && agentName && (
            <span className="text-xs text-content-muted truncate max-w-[120px]">{agentName}</span>
          )}
        </div>

        {/* Agent Selector */}
        {agentEnabled && availableAgents.length > 0 && (
          <select
            value={selectedAgentId || ''}
            onChange={(e) => onSelectAgent?.(e.target.value || null)}
            disabled={isSelectorDisabled}
            className="bg-brand-card/50 border border-brand-border/50 rounded-lg px-3 py-2 text-sm text-content-light focus:outline-none focus:border-primary/50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="">Selecione um agente</option>
            {normalizedAgents.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        )}

        <button className="hidden lg:flex w-10 h-10 rounded-full items-center justify-center text-content-gray hover:text-primary hover:bg-brand-hover transition-colors">
          <MagnifyingGlass weight="regular" className="text-xl" />
        </button>
        <div className="hidden lg:block w-px h-6 bg-brand-border mx-1" />
        <button className="hidden lg:flex w-10 h-10 rounded-full items-center justify-center text-content-gray hover:bg-brand-hover transition-colors">
          <Phone weight="regular" className="text-xl" />
        </button>
        <button className="hidden lg:flex w-10 h-10 rounded-full items-center justify-center text-content-gray hover:bg-brand-hover transition-colors">
          <VideoCamera weight="regular" className="text-xl" />
        </button>
        <div className="hidden lg:block w-px h-6 bg-brand-border mx-1" />
        <button className="hidden lg:flex w-10 h-10 rounded-full items-center justify-center text-content-gray hover:text-white hover:bg-brand-hover transition-colors">
          <DotsThreeVertical weight="regular" className="text-xl" />
        </button>
      </div>
    </header>
  )
}
