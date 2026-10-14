/**
 * JWT Token utilities for authentication
 */

/**
 * Check if a JWT token is expired
 * @param token - JWT token string or null
 * @returns true if token is expired or invalid, false otherwise
 */
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true

  try {
    // JWT tokens have 3 parts separated by dots: header.payload.signature
    const parts = token.split('.')
    if (parts.length !== 3) return true

    // Decode the payload (second part)
    const payload = JSON.parse(atob(parts[1]))
    
    // Check if exp claim exists
    if (!payload.exp) return false

    // Compare expiration time with current time (exp is in seconds)
    return payload.exp * 1000 < Date.now()
  } catch {
    return true
  }
}

/**
 * Sync token to localStorage for API requests
 * @param token - JWT token string or null to clear
 */
export function syncTokenToLocalStorage(token: string | null): void {
  if (typeof window === 'undefined') return

  if (token) {
    localStorage.setItem('token', token)
  } else {
    localStorage.removeItem('token')
  }
}
