import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { isTokenExpired } from '@/lib/authToken'

// Protected routes that require authentication
const PROTECTED_ROUTES = ['/dashboard', '/chat', '/instances', '/qr', '/agent', '/estoque', '/settings']

// Public routes that should redirect authenticated users
const AUTH_ROUTES = ['/login']

export function middleware(request: NextRequest) {
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
    if (pathname !== '/login') {
      loginUrl.searchParams.set('callbackUrl', pathname)
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
      return NextResponse.redirect(new URL('/instances', request.url))
    } else {
      return redirectToLogin()
    }
  }

  // Protect dashboard, chat, instances, and qr routes
  const isProtectedRoute = PROTECTED_ROUTES.some(route => 
    pathname.startsWith(route)
  )
  
  if (isProtectedRoute && !isAuthenticated) {
    return redirectToLogin()
  }

  // Redirect to dashboard if already authenticated and trying to access login
  const isAuthRoute = AUTH_ROUTES.some(route => pathname.startsWith(route))
  
  if (isAuthRoute && isAuthenticated) {
    return NextResponse.redirect(new URL('/instances', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/', '/dashboard/:path*', '/chat/:path*', '/login', '/instances/:path*', '/qr/:path*', '/agent/:path*', '/estoque/:path*', '/settings/:path*'],
}
