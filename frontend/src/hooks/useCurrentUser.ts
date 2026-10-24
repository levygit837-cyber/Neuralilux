'use client'

import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import { authService } from '@/services/authService'
import { useAuthStore } from '@/stores/useAuthStore'

export function useCurrentUser() {
  const token = useAuthStore((state) => state.token)
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => authService.getCurrentUser(token as string),
    enabled: Boolean(token),
  })
}
