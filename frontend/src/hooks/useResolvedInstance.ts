'use client'

import { useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import { ROUTES } from '@/lib/constants'
import { useInstances } from '@/hooks/useInstances'
import type { Instance } from '@/services/instanceService'
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
  const query = useInstances()

  const available = useMemo(() => (query.data ?? []).map(toSelected), [query.data])
  const match = useMemo(
    () =>
      available.find((instance) => instance.id === selectedInstance?.id) ||
      available.find((instance) => instance.status === 'connected') ||
      available[0] ||
      null,
    [available, selectedInstance?.id]
  )
  const resolveError = query.isError
    ? query.error instanceof Error
      ? query.error.message
      : 'Falha ao carregar as instâncias'
    : null
  const isResolvingInstance = query.isPending
  const resolvedInstance = query.isSuccess ? match : selectedInstance

  // Mantém a seleção persistida alinhada com a lista vinda do backend.
  useEffect(() => {
    if (!query.isSuccess) return
    const changed =
      match?.id !== selectedInstance?.id ||
      match?.name !== selectedInstance?.name ||
      match?.status !== selectedInstance?.status
    if (changed) setSelectedInstance(match)
  }, [query.isSuccess, match, selectedInstance, setSelectedInstance])

  useEffect(() => {
    if (!isResolvingInstance && !resolvedInstance && !resolveError) {
      router.push(ROUTES.INSTANCES)
    }
  }, [isResolvingInstance, resolvedInstance, resolveError, router])

  return { resolvedInstance, isResolvingInstance, resolveError }
}
