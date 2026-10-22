'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ROUTES } from '@/lib/constants'
import { instanceService, type Instance } from '@/services/instanceService'
import { useInstanceStore, type SelectedInstance } from '@/stores/useInstanceStore'

const toSelected = (instance: Instance): SelectedInstance => ({
  id: instance.id,
  name: instance.name,
  status: instance.status,
})

/**
 * Resolve a Instance ativa entre as do usuário (`GET /instances/`): prefere a selecionada,
 * depois uma conectada, depois a primeira. Sem nenhuma Instance, leva para `/instances`,
 * onde ele cria a primeira.
 */
export function useResolvedInstance() {
  const router = useRouter()
  const { selectedInstance, setSelectedInstance } = useInstanceStore()
  const [resolvedInstance, setResolvedInstance] = useState<SelectedInstance | null>(selectedInstance)
  const [isResolvingInstance, setIsResolvingInstance] = useState(true)
  const [resolveError, setResolveError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    instanceService
      .list()
      .then((instances) => {
        if (cancelled) return
        const available = instances.map(toSelected)
        const match =
          available.find((instance) => instance.id === selectedInstance?.id) ||
          available.find((instance) => instance.status === 'connected') ||
          available[0] ||
          null

        setResolvedInstance(match)
        setResolveError(null)

        const changed =
          match?.id !== selectedInstance?.id ||
          match?.name !== selectedInstance?.name ||
          match?.status !== selectedInstance?.status
        if (changed) setSelectedInstance(match)
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setResolveError(error instanceof Error ? error.message : 'Falha ao carregar as instâncias')
        setResolvedInstance(selectedInstance)
      })
      .finally(() => {
        if (!cancelled) setIsResolvingInstance(false)
      })

    return () => {
      cancelled = true
    }
  }, [selectedInstance, setSelectedInstance])

  useEffect(() => {
    if (!isResolvingInstance && !resolvedInstance && !resolveError) {
      router.push(ROUTES.INSTANCES)
    }
  }, [isResolvingInstance, resolvedInstance, resolveError, router])

  return { resolvedInstance, isResolvingInstance, resolveError }
}
