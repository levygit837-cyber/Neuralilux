import { Avatar } from '@/components/ui/Avatar'
import { Phone, VideoCamera, MagnifyingGlass, DotsThreeVertical, Robot, Check } from '@phosphor-icons/react'
import type { AgentListItem } from '@/types/agent'

interface ChatHeaderProps {
  name: string
  avatar?: string
  status?: string
  isOnline?: boolean
  agentEnabled?: boolean | null
  agentName?: string | null
  availableAgents?: AgentListItem[]
  selectedAgentId?: string | null
  onSelectAgent?: (agentId: string | null) => void
  onToggleAgent?: () => void
  isAgentLoading?: boolean
  isAgentBindingLoading?: boolean
}

export function ChatHeader({
  name,
  avatar,
  status,
  isOnline,
  agentEnabled,
  agentName,
  availableAgents = [],
  selectedAgentId,
  onSelectAgent,
  onToggleAgent,
  isAgentLoading = false,
  isAgentBindingLoading = false,
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
    <header className="h-20 glass-header border-b border-brand-border/50 px-6 flex items-center justify-between z-20">
      {/* Contact Info */}
      <div className="flex items-center gap-4 cursor-pointer group">
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
      <div className="flex items-center gap-2">
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

        <button className="w-10 h-10 rounded-full flex items-center justify-center text-content-gray hover:text-primary hover:bg-brand-hover transition-colors">
          <MagnifyingGlass weight="regular" className="text-xl" />
        </button>
        <div className="w-px h-6 bg-brand-border mx-1" />
        <button className="w-10 h-10 rounded-full flex items-center justify-center text-content-gray hover:bg-brand-hover transition-colors">
          <Phone weight="regular" className="text-xl" />
        </button>
        <button className="w-10 h-10 rounded-full flex items-center justify-center text-content-gray hover:bg-brand-hover transition-colors">
          <VideoCamera weight="regular" className="text-xl" />
        </button>
        <div className="w-px h-6 bg-brand-border mx-1" />
        <button className="w-10 h-10 rounded-full flex items-center justify-center text-content-gray hover:text-white hover:bg-brand-hover transition-colors">
          <DotsThreeVertical weight="regular" className="text-xl" />
        </button>
      </div>
    </header>
  )
}
