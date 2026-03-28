import { Avatar } from '@/components/ui/Avatar'
import { MoreVertical, Phone, Bot, Power, Loader2 } from 'lucide-react'
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
    <div className="flex items-center justify-between border-b border-border-color bg-card px-6 py-4">
      <div className="flex items-center gap-4">
        <Avatar
          src={avatar}
          fallback={name.substring(0, 2).toUpperCase()}
          size="md"
        />
        <div>
          <h2 className="text-base font-semibold text-text-light">{name}</h2>
          {status && (
            <div className="flex items-center gap-2">
              {isOnline !== undefined && (
                <span
                  className={`h-2 w-2 rounded-full ${
                    isOnline ? 'bg-green-500' : 'bg-gray-500'
                  }`}
                />
              )}
              <p className="text-xs text-text-muted">{status}</p>
            </div>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {onSelectAgent && (
          <div className="hidden items-center gap-2 rounded-lg bg-hover px-3 py-2 md:flex">
            <Bot className="h-4 w-4 text-text-gray" />
            <select
              value={selectedAgentId ?? ''}
              onChange={(event) => onSelectAgent(event.target.value || null)}
              disabled={isSelectorDisabled}
              className="min-w-[180px] bg-transparent text-sm text-text-light outline-none disabled:cursor-not-allowed disabled:opacity-60"
              title="Selecione o agente que responderá automaticamente nesta instância"
            >
              <option value="" className="bg-card text-text-light">
                Sem agente vinculado
              </option>
              {normalizedAgents.map((agent) => (
                <option key={agent.id} value={agent.id} className="bg-card text-text-light">
                  {agent.name}
                </option>
              ))}
            </select>
          </div>
        )}
        {/* Agent Toggle Button */}
        {onToggleAgent && (
          <button
            onClick={onToggleAgent}
            disabled={isButtonDisabled}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isAgentLoading
                ? 'bg-yellow-500/20 text-yellow-300'
                : agentEnabled
                ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                : 'bg-gray-500/20 text-gray-400 hover:bg-gray-500/30'
            } ${isButtonDisabled ? 'cursor-not-allowed opacity-80' : ''}`}
            title={
              isAgentLoading
                ? 'Carregando status do agente'
                : agentEnabled
                ? 'Agente ativado - Clique para desativar'
                : 'Agente desativado - Clique para ativar'
            }
          >
            {isAgentLoading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="hidden sm:inline">Atualizando...</span>
              </>
            ) : agentEnabled ? (
              <>
                <Bot className="h-4 w-4" />
                <span className="hidden sm:inline">Agente ON</span>
              </>
            ) : (
              <>
                <Power className="h-4 w-4" />
                <span className="hidden sm:inline">Agente OFF</span>
              </>
            )}
          </button>
        )}
        <button className="flex h-10 w-10 items-center justify-center rounded-lg bg-hover text-text-gray transition-colors hover:bg-border">
          <Phone className="h-5 w-5" />
        </button>
        <button className="flex h-10 w-10 items-center justify-center rounded-lg bg-hover text-text-gray transition-colors hover:bg-border">
          <MoreVertical className="h-5 w-5" />
        </button>
      </div>
    </div>
  )
}
