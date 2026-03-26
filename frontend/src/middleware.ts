import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Get auth token from cookie or localStorage (in real app)
  // For now, we'll check if there's an auth-storage cookie
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

  // Protect dashboard and chat routes
  if ((pathname.startsWith('/dashboard') || pathname.startsWith('/chat')) && !isAuthenticated) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  // Redirect to dashboard if already authenticated and trying to access login
  if (pathname === '/login' && isAuthenticated) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/dashboard/:path*', '/chat/:path*', '/login'],
}
