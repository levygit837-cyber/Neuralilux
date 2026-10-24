import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { buildCsp } from '@/lib/csp'
import { API_BASE_URL, API_INTERNAL_URL, AUTH_COOKIE_NAME, POST_LOGIN_ROUTE, ROUTES, WS_URL } from '@/lib/constants'

const SESSION_CHECK_TIMEOUT_MS = 3000

/** `valid`: o backend aceitou o cookie. `invalid`: recusou (forjado, vencido, usuário inativo). `unavailable`: sem resposta. */
type SessionState = 'none' | 'valid' | 'invalid' | 'unavailable'

/**
 * A sessão só vale se o backend a aceitar: o proxy não lê nem decodifica o JWT, entrega o cookie ao `/auth/me`,
 * que verifica assinatura, prazo e se o usuário segue ativo. Cookie forjado, vencido ou de usuário desativado não passa.
 */
async function sessionState(request: NextRequest): Promise<SessionState> {
  const cookie = request.cookies.get(AUTH_COOKIE_NAME)?.value
  if (!cookie) return 'none'
  try {
    const response = await fetch(`${API_INTERNAL_URL}/api/v1/auth/me`, {
      headers: { Cookie: `${AUTH_COOKIE_NAME}=${cookie}` },
      cache: 'no-store',
      signal: AbortSignal.timeout(SESSION_CHECK_TIMEOUT_MS),
    })
    if (response.ok) return 'valid'
    return response.status === 401 ? 'invalid' : 'unavailable'
  } catch {
    return 'unavailable'
  }
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const session = await sessionState(request)
  const isAuthenticated = session === 'valid'

  // Cookie que o backend recusou não serve para mais nada: sai do navegador. Backend fora do ar não apaga nada.
  const finish = (response: NextResponse) => {
    if (session === 'invalid') response.cookies.delete(AUTH_COOKIE_NAME)
    return response
  }

  const redirectToLogin = () => {
    const loginUrl = new URL(ROUTES.LOGIN, request.url)
    if (pathname !== ROUTES.HOME) {
      loginUrl.searchParams.set('callbackUrl', `${pathname}${request.nextUrl.search}`)
    }
    return finish(NextResponse.redirect(loginUrl))
  }

  if (pathname === ROUTES.HOME) {
    return isAuthenticated ? NextResponse.redirect(new URL(POST_LOGIN_ROUTE, request.url)) : redirectToLogin()
  }

  const isLogin = pathname === ROUTES.LOGIN
  // Tudo fora de /login exige sessão válida, inclusive URLs desconhecidas e com ponto (/dashboard.json, /chat/a.b).
  if (!isLogin && !isAuthenticated) return redirectToLogin()
  if (isLogin && isAuthenticated) return NextResponse.redirect(new URL(POST_LOGIN_ROUTE, request.url))

  // CSP com nonce por requisição: o Next lê o nonce do cabeçalho da requisição e o aplica aos scripts.
  const nonce = Buffer.from(crypto.randomUUID()).toString('base64')
  const csp = buildCsp({ nonce, isDev: process.env.NODE_ENV === 'development', apiUrl: API_BASE_URL, wsUrl: WS_URL })
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set('x-nonce', nonce)
  requestHeaders.set('Content-Security-Policy', csp)

  const response = NextResponse.next({ request: { headers: requestHeaders } })
  response.headers.set('Content-Security-Policy', csp)
  return finish(response)
}

export const config = {
  // Só os arquivos do próprio Next (JS/CSS com hash e o otimizador de imagem) e o ícone ficam fora. Qualquer outro
  // caminho passa pelo proxy, também os com ponto: `.*\..*` deixava `/dashboard.json` chegar ao layout sem sessão.
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
}
