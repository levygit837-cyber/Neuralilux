import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { buildCsp } from '@/lib/csp'
import { AUTH_COOKIE_DOMAIN, AUTH_COOKIE_NAME, API_BASE_URL, POST_LOGIN_ROUTE, ROUTES, WS_URL } from '@/lib/constants'
import { checkSession } from '@/lib/session'

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const session = await checkSession(request.cookies.get(AUTH_COOKIE_NAME)?.value)
  const isAuthenticated = session === 'valid'

  // Cookie que o backend recusou não serve para mais nada: sai do navegador. Backend fora do ar não apaga nada.
  // O cookie só é apagado com o mesmo `domain` e `path` com que foi gravado (`AUTH_COOKIE_DOMAIN` no backend).
  const finish = (response: NextResponse) => {
    if (session === 'invalid') {
      response.cookies.delete({ name: AUTH_COOKIE_NAME, path: '/', ...(AUTH_COOKIE_DOMAIN && { domain: AUTH_COOKIE_DOMAIN }) })
    }
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
  // O matcher casa por prefixo: sem `(?:/|$)` e `$`, `/_next/staticfoo` e `/favicon.ico.json` escapariam do proxy.
  matcher: ['/((?!(?:_next/static|_next/image)(?:/|$)|favicon\\.ico$).*)'],
}
