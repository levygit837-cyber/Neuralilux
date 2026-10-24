import { afterEach, describe, expect, it, vi } from 'vitest'
import { isTokenExpired } from '@/lib/authToken'

const NOW = Date.UTC(2026, 9, 24, 12, 0, 0)

function tokenWith(payload: object): string {
  return `h.${btoa(JSON.stringify(payload))}.s`
}

describe('isTokenExpired', () => {
  afterEach(() => vi.useRealTimers())

  it('trata ausência de token como expirado', () => {
    expect(isTokenExpired(null)).toBe(true)
    expect(isTokenExpired('')).toBe(true)
  })

  it('trata token malformado como expirado', () => {
    expect(isTokenExpired('so-uma-parte')).toBe(true)
    expect(isTokenExpired('a.b')).toBe(true)
    expect(isTokenExpired('a.%%%.c')).toBe(true)
  })

  it('compara exp (em segundos) com o relógio', () => {
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    const nowSeconds = NOW / 1000
    expect(isTokenExpired(tokenWith({ exp: nowSeconds + 60 }))).toBe(false)
    expect(isTokenExpired(tokenWith({ exp: nowSeconds - 1 }))).toBe(true)
  })

  it('token sem exp não expira', () => {
    expect(isTokenExpired(tokenWith({ sub: 'u1' }))).toBe(false)
  })
})
