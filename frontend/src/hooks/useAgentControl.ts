'use client'

import { useCallback, useEffect, useState } from 'react'
import { agentService } from '@/services/agentService'
import { instanceService } from '@/services/instanceService'
import type { AgentListItem } from '@/types/chat'

const NO_AGENTS: AgentListItem[] = []

interface AgentBinding {
  token: string | null
  id: string | null
  name: string | null
}

const messageOf = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback)

/** Estado do Agent da Instance: ligado/desligado, Agent vinculado e a lista de Agents disponíveis. */
export function useAgentControl(instanceName: string | undefined, token: string | null) {
  const [agentEnabled, setAgentEnabled] = useState<boolean | null>(null)
  const [fetchedAgents, setFetchedAgents] = useState<AgentListItem[]>([])
  // O vínculo guarda o token com que foi lido; sem token, ou com outro token, ele some no render.
  const [binding, setBinding] = useState<AgentBinding>({ token: null, id: null, name: null })
  const [isStatusLoading, setIsStatusLoading] = useState(false)
  const [isAgentsLoading, setIsAgentsLoading] = useState(false)
  const [isBinding, setIsBinding] = useState(false)
  const [isToggling, setIsToggling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const availableAgents = token ? fetchedAgents : NO_AGENTS
  const hasCurrentBinding = token !== null && binding.token === token
  const selectedAgentId = hasCurrentBinding ? binding.id : null
  const selectedAgentName = hasCurrentBinding ? binding.name : null

  useEffect(() => {
    if (!token) return
    let cancelled = false

    const loadAgents = async () => {
      setIsAgentsLoading(true)
      try {
        const response = await agentService.getAgents()
        if (!cancelled) setFetchedAgents(response.items)
      } catch {
        if (!cancelled) setError('Nao foi possivel carregar a lista de agentes disponiveis.')
      } finally {
        if (!cancelled) setIsAgentsLoading(false)
      }
    }

    void loadAgents()
    return () => {
      cancelled = true
    }
  }, [token])

  useEffect(() => {
    if (!instanceName) return
    let cancelled = false

    const loadStatus = async () => {
      setIsStatusLoading(true)
      setError(null)
      setAgentEnabled(null)
      try {
        const status = await instanceService.getAgentStatus(instanceName)
        if (cancelled) return
        setAgentEnabled(status.agent_enabled)
        setBinding({ token, id: status.agent_id, name: status.agent_name ?? null })
      } catch (e) {
        if (!cancelled) setError(messageOf(e, 'Nao foi possivel carregar o status do agente para esta instancia.'))
      } finally {
        if (!cancelled) setIsStatusLoading(false)
      }
    }

    void loadStatus()
    return () => {
      cancelled = true
    }
  }, [instanceName, token])

  const toggleAgent = useCallback(async () => {
    if (!instanceName || agentEnabled === null || isToggling) return
    if (!agentEnabled && !selectedAgentId) {
      setError('Selecione um agente antes de ativar as respostas automáticas.')
      return
    }

    setError(null)
    setIsToggling(true)
    try {
      const response = await instanceService.updateAgentStatus(instanceName, !agentEnabled)
      setAgentEnabled(response.agent_enabled)
    } catch (e) {
      setError(messageOf(e, 'Nao foi possivel atualizar o status do agente. Tente novamente.'))
    } finally {
      setIsToggling(false)
    }
  }, [instanceName, agentEnabled, selectedAgentId, isToggling])

  const selectAgent = useCallback(
    async (nextAgentId: string | null) => {
      if (!instanceName || isBinding || nextAgentId === selectedAgentId) return

      setError(null)
      setIsBinding(true)
      try {
        const response = await instanceService.updateAgentBinding(instanceName, nextAgentId)
        setBinding({
          token,
          id: response.agent_id,
          name: response.agent_name ?? availableAgents.find((agent) => agent.id === response.agent_id)?.name ?? null,
        })
        setAgentEnabled(response.agent_enabled)
      } catch (e) {
        setError(messageOf(e, 'Nao foi possivel atualizar o agente vinculado. Tente novamente.'))
      } finally {
        setIsBinding(false)
      }
    },
    [instanceName, isBinding, selectedAgentId, availableAgents, token]
  )

  return {
    agentEnabled,
    availableAgents,
    selectedAgentId,
    selectedAgentName,
    isAgentLoading: isStatusLoading || isToggling,
    isBindingLoading: isAgentsLoading || isBinding,
    error,
    toggleAgent,
    selectAgent,
  }
}
