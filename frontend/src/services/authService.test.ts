import { describe, expect, it } from 'vitest'
import { loginErrorMessage } from '@/services/authService'

const response = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(typeof body === 'string' ? body : JSON.stringify(body), { status, headers })

describe('loginErrorMessage', () => {
  it('429 diz quanto esperar a partir de Retry-After', async () => {
    const message = await loginErrorMessage(
      response(429, { detail: 'Too many attempts, try again later' }, { 'Retry-After': '42' })
    )
    expect(message).toBe('Muitas tentativas de login. Tente de novo em 42 s.')
  })

  it('429 sem Retry-After válido não inventa tempo', async () => {
    const message = await loginErrorMessage(response(429, {}, { 'Retry-After': 'abc' }))
    expect(message).toBe('Muitas tentativas de login. Tente de novo em instantes.')
  })

  it('503 (rate limit sem Redis) vira indisponibilidade, sem expor o detail', async () => {
    const message = await loginErrorMessage(response(503, { detail: 'Service temporarily unavailable' }))
    expect(message).toBe('Login indisponível no momento. Tente de novo em instantes.')
  })

  it('401 usa o detail do backend', async () => {
    expect(await loginErrorMessage(response(401, { detail: 'Incorrect email or password' }))).toBe(
      'Incorrect email or password'
    )
  })

  it('corpo sem JSON cai no fallback em vez de estourar', async () => {
    expect(await loginErrorMessage(response(502, '<html>'))).toBe('Erro ao fazer login')
  })
})
