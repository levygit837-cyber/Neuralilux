import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

// Protected routes that require authentication
const PROTECTED_ROUTES = ['/dashboard', '/chat', '/instances', '/qr']

// Public routes that should redirect authenticated users
const AUTH_ROUTES = ['/login']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Get auth token from cookie (persisted by Zustand)
  const authStorage = request.cookies.get('auth-storage')

  let isAuthenticated = false
  if (authStorage) {
    try {
      const parsed = JSON.parse(authStorage.value)
      isAuthenticated = parsed.state?.isAuthenticated || false
    } catch {
      isAuthenticated = false
    }
  }

  // Root route - redirect based on auth state
  if (pathname === '/') {
    if (isAuthenticated) {
      return NextResponse.redirect(new URL('/instances', request.url))
    } else {
      return NextResponse.redirect(new URL('/login', request.url))
    }
  }

  // Protect dashboard, chat, instances, and qr routes
  const isProtectedRoute = PROTECTED_ROUTES.some(route => 
    pathname.startsWith(route)
  )
  
  if (isProtectedRoute && !isAuthenticated) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('callbackUrl', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Redirect to dashboard if already authenticated and trying to access login
  const isAuthRoute = AUTH_ROUTES.some(route => pathname.startsWith(route))
  
  if (isAuthRoute && isAuthenticated) {
    return NextResponse.redirect(new URL('/instances', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/', '/dashboard/:path*', '/chat/:path*', '/login', '/instances/:path*', '/qr/:path*'],
}
