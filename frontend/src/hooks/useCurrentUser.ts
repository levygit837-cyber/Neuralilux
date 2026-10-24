'use client'

import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { authService } from '@/services/authService'
import { useSessionReady } from '@/hooks/useSessionReady'

export function useCurrentUser() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: authService.getCurrentUser,
    enabled: useSessionReady(),
  })
}
