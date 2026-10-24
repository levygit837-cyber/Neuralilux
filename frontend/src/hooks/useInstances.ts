'use client'

import { useQuery } from '@tanstack/react-query'
import { useSessionReady } from '@/hooks/useSessionReady'
import { queryKeys } from '@/lib/queryKeys'
import { instanceService } from '@/services/instanceService'

/** Instances do usuário; a mesma query alimenta Instances, Configurações e a resolução da Instance ativa. */
export function useInstances() {
  const enabled = useSessionReady()
  return useQuery({ queryKey: queryKeys.instances, queryFn: instanceService.list, enabled })
}
