import { NextRequest } from 'next/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { config, proxy } from '@/proxy'
import { AUTH_COOKIE_NAME } from '@/lib/constants'

const ORIGIN = 'http://localhost:3000'

function request(path: string, cookie?: string) {
  return new NextRequest(`${ORIGIN}${path}`, cookie ? { headers: { cookie: `${AUTH_COOKIE_NAME}=${cookie}` } } : undefined)
}

/** O backend responde `/auth/me` com o status dado; devolve o mock para inspecionar a chamada. */
function backendAnswers(status: number) {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const redirectTarget = (response: Response) => {
  const location = response.headers.get('location')
  return location ? new URL(location) : null
}

afterEach(() => vi.unstubAllGlobals())

describe('proxy: sessão validada no backend', () => {
  it('cookie forjado (o backend recusa) não abre página autenticada e é apagado', async () => {
    backendAnswers(401)
    const response = await proxy(request('/dashboard', 'jwt-forjado'))

    const target = redirectTarget(response)
    expect(target?.pathname).toBe('/login')
    expect(target?.searchParams.get('callbackUrl')).toBe('/dashboard')
    expect(response.headers.get('set-cookie')).toMatch(new RegExp(`${AUTH_COOKIE_NAME}=;`))
  })

  it('entrega o cookie ao backend em /auth/me', async () => {
    const fetchMock = backendAnswers(200)
    await proxy(request('/dashboard', 'abc'))

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/v1\/auth\/me$/)
    expect(init.headers.Cookie).toBe(`${AUTH_COOKIE_NAME}=abc`)
  })

  it('sessão aceita pelo backend passa e recebe a CSP com nonce', async () => {
    backendAnswers(200)
    const response = await proxy(request('/dashboard', 'valido'))

    expect(response.headers.get('location')).toBeNull()
    expect(response.headers.get('content-security-policy')).toMatch(/script-src 'self' 'nonce-[^']+' 'strict-dynamic'/)
    expect(response.headers.get('content-security-policy')).toContain("frame-ancestors 'none'")
  })

  it('cada requisição recebe um nonce diferente', async () => {
    backendAnswers(200)
    const nonceOf = async () =>
      (await proxy(request('/dashboard', 'valido'))).headers.get('content-security-policy')!.match(/'nonce-([^']+)'/)![1]
    expect(await nonceOf()).not.toBe(await nonceOf())
  })

  it('sem cookie nem chama o backend e vai para o login', async () => {
    const fetchMock = backendAnswers(200)
    const response = await proxy(request('/pedidos'))

    expect(fetchMock).not.toHaveBeenCalled()
    expect(redirectTarget(response)?.pathname).toBe('/login')
  })

  it.each(['/dashboard.json', '/chat/a.b', '/qualquer.coisa', '/pedidos/1.2', '/robots.txt'])(
    '%s sem sessão não renderiza nada: vai para o login',
    async (path) => {
      const response = await proxy(request(path))
      expect(redirectTarget(response)?.pathname).toBe('/login')
    }
  )

  it('backend fora do ar não vale como sessão, mas também não apaga o cookie', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')))
    const response = await proxy(request('/dashboard', 'valido'))

    expect(redirectTarget(response)?.pathname).toBe('/login')
    expect(response.headers.get('set-cookie')).toBeNull()
  })

  it('erro 5xx do backend também não apaga o cookie', async () => {
    backendAnswers(503)
    const response = await proxy(request('/dashboard', 'valido'))

    expect(redirectTarget(response)?.pathname).toBe('/login')
    expect(response.headers.get('set-cookie')).toBeNull()
  })

  it('/login é aberto sem sessão, com CSP', async () => {
    const response = await proxy(request('/login'))
    expect(response.headers.get('location')).toBeNull()
    expect(response.headers.get('content-security-policy')).toBeTruthy()
  })

  it('/login com sessão válida leva ao painel', async () => {
    backendAnswers(200)
    expect(redirectTarget(await proxy(request('/login', 'valido')))?.pathname).toBe('/dashboard')
  })

  it('/login com cookie forjado continua aberto (e apaga o cookie)', async () => {
    backendAnswers(401)
    const response = await proxy(request('/login', 'forjado'))
    expect(response.headers.get('location')).toBeNull()
    expect(response.headers.get('set-cookie')).toMatch(new RegExp(`${AUTH_COOKIE_NAME}=;`))
  })

  it('a raiz vai para o painel com sessão e para o login sem ela', async () => {
    backendAnswers(200)
    expect(redirectTarget(await proxy(request('/', 'valido')))?.pathname).toBe('/dashboard')
    expect(redirectTarget(await proxy(request('/')))?.pathname).toBe('/login')
    expect(redirectTarget(await proxy(request('/')))?.searchParams.has('callbackUrl')).toBe(false)
  })
})

describe('proxy: cookie recusado com AUTH_COOKIE_DOMAIN', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.resetModules()
  })

  it('apaga o cookie com o mesmo domain com que o backend o gravou', async () => {
    vi.stubEnv('AUTH_COOKIE_DOMAIN', '.exemplo.com')
    vi.resetModules()
    const { proxy: proxyWithDomain } = await import('@/proxy')
    backendAnswers(401)

    const response = await proxyWithDomain(request('/dashboard', 'jwt-forjado'))

    const header = response.headers.get('set-cookie') ?? ''
    expect(header).toMatch(new RegExp(`${AUTH_COOKIE_NAME}=;`))
    expect(header.toLowerCase()).toContain('domain=.exemplo.com')
  })

  it('sem AUTH_COOKIE_DOMAIN apaga o cookie sem domain', async () => {
    backendAnswers(401)
    const response = await proxy(request('/dashboard', 'jwt-forjado'))

    expect((response.headers.get('set-cookie') ?? '').toLowerCase()).not.toContain('domain=')
  })
})

describe('proxy: o matcher só deixa de fora arquivos do Next', () => {
  const [source] = config.matcher
  const matches = (path: string) => new RegExp(`^${source}$`).test(path)

  it.each(['/_next/static/chunks/main.js', '/_next/image', '/favicon.ico'])('%s fica fora', (path) => {
    expect(matches(path)).toBe(false)
  })

  it.each([
    '/dashboard',
    '/dashboard.json',
    '/chat/a.b',
    '/login',
    '/',
    '/api/qualquer',
    '/robots.txt',
    '/_nextfoo',
    '/favicon.ico.json',
    '/favicon.ico/x',
    '/faviconXico',
    '/_next/staticfoo',
    '/_next/image.json',
  ])('%s passa pelo proxy', (path) => {
    expect(matches(path)).toBe(true)
  })
})
