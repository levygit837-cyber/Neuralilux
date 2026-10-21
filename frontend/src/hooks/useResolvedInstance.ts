'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ROUTES } from '@/lib/constants'
import { instanceService, type EvolutionInstance } from '@/services/instanceService'
import { useInstanceStore, type SelectedInstance } from '@/stores/useInstanceStore'

const toSelectedInstance = (instance: EvolutionInstance): SelectedInstance => ({
  instanceName: instance.instance.instanceName,
  instanceId: instance.instance.instanceId,
  status: instance.instance.state || instance.socket?.state || 'close',
})

/**
 * Resolve a Instance ativa: prefere a selecionada (por id ou nome), depois uma
 * conectada, depois a primeira. Persiste a escolha no store e volta para a home
 * quando a Company não tem nenhuma Instance.
 */
export function useResolvedInstance() {
  const router = useRouter()
  const { selectedInstance, setSelectedInstance } = useInstanceStore()
  const [resolvedInstance, setResolvedInstance] = useState<SelectedInstance | null>(selectedInstance)
  const [isResolvingInstance, setIsResolvingInstance] = useState(true)

  useEffect(() => {
    let cancelled = false

    instanceService
      .fetchInstances()
      .then((instances) => {
        if (cancelled) return
        const available = instances.map(toSelectedInstance)

        if (available.length === 0) {
          setResolvedInstance(null)
          return
        }

        const selectedName = selectedInstance?.instanceName?.toLowerCase()
        const match =
          available.find(
            (instance) =>
              instance.instanceId === selectedInstance?.instanceId ||
              instance.instanceName.toLowerCase() === selectedName
          ) ||
          available.find((instance) => instance.status === 'open') ||
          available[0]

        setResolvedInstance(match)

        if (
          !selectedInstance ||
          match.instanceId !== selectedInstance.instanceId ||
          match.instanceName !== selectedInstance.instanceName ||
          match.status !== selectedInstance.status
        ) {
          setSelectedInstance(match)
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return
        console.error('Failed to resolve active instance:', error)
        setResolvedInstance(selectedInstance ?? null)
      })
      .finally(() => {
        if (!cancelled) setIsResolvingInstance(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedInstance, setSelectedInstance])

  useEffect(() => {
    if (!isResolvingInstance && !resolvedInstance) {
      router.push(ROUTES.HOME)
    }
  }, [isResolvingInstance, resolvedInstance, router])

  return { resolvedInstance, isResolvingInstance }
}
