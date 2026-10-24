import { describe, expect, it } from 'vitest'
import { POST_LOGIN_ROUTE } from '@/lib/constants'
import { safeCallbackUrl } from '@/lib/safeCallbackUrl'

describe('safeCallbackUrl', () => {
  it.each(['/chat', '/pedidos?filter=done', '/qr/abc#top'])('aceita path interno %s', (path) => {
    expect(safeCallbackUrl(path)).toBe(path)
  })

  it.each([
    'https://evil.example/phish',
    'http://evil.example',
    '//evil.example',
    '/\\evil.example',
    '\\\\evil.example',
    'javascript:alert(1)',
    'chat',
    '/\t/evil.example',
    '/%2F%2Fevil.example',
    '/%5Cevil.example',
    '/ /x',
    ' /x',
    '/%E0%A4%A',
    '/',
    '/?x=1',
    '/login',
    '/login?callbackUrl=/chat',
    '',
  ])('ignora destino inseguro %j', (value) => {
    expect(safeCallbackUrl(value)).toBe(POST_LOGIN_ROUTE)
  })

  it('usa o padrão quando ausente', () => {
    expect(safeCallbackUrl(null)).toBe(POST_LOGIN_ROUTE)
    expect(safeCallbackUrl(undefined)).toBe(POST_LOGIN_ROUTE)
  })

  it('usa o primeiro valor quando o parâmetro se repete', () => {
    expect(safeCallbackUrl(['/chat', 'https://evil.example'])).toBe('/chat')
  })
})
