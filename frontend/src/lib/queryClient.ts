import { QueryClient, isServer } from '@tanstack/react-query'

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

let browserClient: QueryClient | undefined

/** No servidor, um cliente por chamada (nunca compartilhado entre usuários); no browser, um só. */
export function getQueryClient(): QueryClient {
  if (isServer) return createQueryClient()
  browserClient ??= createQueryClient()
  return browserClient
}

/**
 * Descarta todo o cache. Chamado na fronteira da sessão (`useAuthStore.login` e `logout`, que o
 * 401 também usa): os dados em cache são de quem estava logado e não podem aparecer para o próximo.
 */
export function clearQueryCache(): void {
  browserClient?.clear()
}
