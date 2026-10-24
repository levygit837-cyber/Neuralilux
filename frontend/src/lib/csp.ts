interface CspOptions {
  nonce: string
  isDev: boolean
  /** URLs do backend (HTTP e Socket.IO): os únicos destinos externos de `fetch`/WebSocket da página. */
  apiUrl: string
  wsUrl: string
}

const originOf = (url: string): string => new URL(url).origin

/**
 * Content-Security-Policy de cada resposta (ADR 0008). Scripts só com o nonce da requisição; `'strict-dynamic'`
 * deixa os chunks do Next carregarem os demais. `style-src-attr 'unsafe-inline'` existe porque o React renderiza
 * `style={{…}}` como atributo no HTML do servidor (barras e gráficos); atributo de estilo não executa script.
 */
export function buildCsp({ nonce, isDev, apiUrl, wsUrl }: CspOptions): string {
  const api = originOf(apiUrl)
  const ws = originOf(wsUrl.replace(/^http/i, 'ws')).replace(/^http/i, 'ws')
  // O Socket.IO começa em polling HTTP e sobe para WebSocket; o mesmo host nos dois esquemas.
  const connect = new Set(["'self'", api, ws, api.replace(/^http/i, 'ws'), ws.replace(/^ws/i, 'http')])

  const directives: Record<string, string[]> = {
    'default-src': ["'self'"],
    'script-src': ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'", ...(isDev ? ["'unsafe-eval'"] : [])],
    'style-src': ["'self'", `'nonce-${nonce}'`],
    'style-src-attr': ["'unsafe-inline'"],
    // Fotos de perfil do WhatsApp (https) e, em desenvolvimento, imagens locais.
    'img-src': ["'self'", 'blob:', 'data:', 'https:', ...(isDev ? ['http://localhost:*'] : [])],
    'font-src': ["'self'"],
    'connect-src': [...connect],
    'object-src': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
    'frame-ancestors': ["'none'"],
  }
  return Object.entries(directives)
    .map(([name, sources]) => `${name} ${sources.join(' ')}`)
    .join('; ')
}
