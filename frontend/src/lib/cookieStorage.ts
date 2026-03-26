import type { StateStorage } from 'zustand/middleware'

// Helper para ler cookie pelo nome
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  
  const cookies = document.cookie.split(';')
  for (const cookie of cookies) {
    const [cookieName, cookieValue] = cookie.trim().split('=')
    if (cookieName === name) {
      return decodeURIComponent(cookieValue)
    }
  }
  return null
}

// Helper para definir cookie
function setCookie(name: string, value: string, days = 7): void {
  if (typeof document === 'undefined') return
  
  const expires = new Date()
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000)
  document.cookie = `${name}=${encodeURIComponent(value)};expires=${expires.toUTCString()};path=/;SameSite=Lax`
}

// Helper para remover cookie
function removeCookie(name: string): void {
  if (typeof document === 'undefined') return
  
  document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`
}

// Storage customizado do Zustand usando cookies
export const cookieStorage: StateStorage = {
  getItem: (name: string): string | null => {
    const value = getCookie(name)
    return value
  },
  setItem: (name: string, value: string): void => {
    setCookie(name, value)
  },
  removeItem: (name: string): void => {
    removeCookie(name)
  },
}

export { getCookie, setCookie, removeCookie }
