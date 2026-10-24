import { QueryClient } from '@tanstack/react-query'

/**
 * Cliente de queries do painel. Sem retry: o erro do backend (inclusive 401, que a camada HTTP
 * já trata encerrando a sessão) aparece na tela em vez de ficar escondido atrás de tentativas.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 30_000 },
    },
  })
}
