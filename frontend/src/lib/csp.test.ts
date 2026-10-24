import { describe, expect, it } from 'vitest'
import { buildCsp } from '@/lib/csp'

const base = { nonce: 'abc123', isDev: false, apiUrl: 'https://api.exemplo.com', wsUrl: 'wss://api.exemplo.com' }
const directive = (csp: string, name: string) => csp.split('; ').find((part) => part.startsWith(`${name} `)) ?? ''

describe('buildCsp', () => {
  it('scripts só com o nonce: sem unsafe-inline nem unsafe-eval em produção', () => {
    const scripts = directive(buildCsp(base), 'script-src')
    expect(scripts).toContain("'nonce-abc123'")
    expect(scripts).not.toContain('unsafe-inline')
    expect(scripts).not.toContain('unsafe-eval')
  })

  it('unsafe-eval só em desenvolvimento', () => {
    expect(directive(buildCsp({ ...base, isDev: true }), 'script-src')).toContain("'unsafe-eval'")
  })

  it('proíbe ser embutido em frame, plugins e base alheia', () => {
    const csp = buildCsp(base)
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).toContain("object-src 'none'")
    expect(csp).toContain("base-uri 'self'")
    expect(csp).toContain("form-action 'self'")
  })

  it('connect-src libera a API e o Socket.IO em http e ws, e nada mais', () => {
    const connect = directive(buildCsp(base), 'connect-src').split(' ')
    expect(connect).toEqual(
      expect.arrayContaining(["'self'", 'https://api.exemplo.com', 'wss://api.exemplo.com'])
    )
    expect(connect).not.toContain('*')
  })

  it('API local em http libera ws do mesmo host', () => {
    const connect = directive(
      buildCsp({ ...base, apiUrl: 'http://localhost:8100', wsUrl: 'ws://localhost:8100' }),
      'connect-src'
    )
    expect(connect).toContain('http://localhost:8100')
    expect(connect).toContain('ws://localhost:8100')
  })
})
