import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { isTokenExpired } from '@/lib/authToken'
import { POST_LOGIN_ROUTE } from '@/lib/constants'

// Public routes that should redirect authenticated users
const AUTH_ROUTES = ['/login']

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Get auth token from cookie (persisted by Zustand)
  const authStorage = request.cookies.get('auth-storage')

  let isAuthenticated = false
  let hasExpiredToken = false
  if (authStorage) {
    try {
      const parsed = JSON.parse(authStorage.value)
      const token = typeof parsed.state?.token === 'string' ? parsed.state.token : null
      hasExpiredToken = Boolean(token) && isTokenExpired(token)
      isAuthenticated = Boolean(parsed.state?.isAuthenticated) && Boolean(token) && !hasExpiredToken
    } catch {
      isAuthenticated = false
    }
  }

  const redirectToLogin = () => {
    const loginUrl = new URL('/login', request.url)
    if (pathname !== '/login' && pathname !== '/') {
      loginUrl.searchParams.set('callbackUrl', `${pathname}${request.nextUrl.search}`)
    }

    const response = NextResponse.redirect(loginUrl)
    if (authStorage && hasExpiredToken) {
      response.cookies.delete('auth-storage')
    }
    return response
  }

  // Root route - redirect based on auth state
  if (pathname === '/') {
    if (isAuthenticated) {
      return NextResponse.redirect(new URL(POST_LOGIN_ROUTE, request.url))
    } else {
      return redirectToLogin()
    }
  }

  // Tudo fora de /login exige sessão, inclusive URLs desconhecidas (o 404 com Sidebar é só para logado).
  const isAuthRoute = AUTH_ROUTES.some(route => pathname.startsWith(route))

  if (!isAuthRoute && !isAuthenticated) {
    return redirectToLogin()
  }

  // Redirect to the post-login route if already authenticated and trying to access login
  if (isAuthRoute && isAuthenticated) {
    return NextResponse.redirect(new URL(POST_LOGIN_ROUTE, request.url))
  }

  return NextResponse.next()
}

export const config = {
  // Exclui estáticos do Next e arquivos com extensão (favicon, imagens).
  matcher: ['/((?!_next/|api/|.*\\..*).*)'],
}
