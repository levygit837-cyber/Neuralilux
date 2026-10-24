import { afterEach, describe, expect, it, vi } from 'vitest'
import { authService, loginErrorMessage } from '@/services/authService'
import { apiRequest } from '@/services/http'

afterEach(() => vi.unstubAllGlobals())

const response = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(typeof body === 'string' ? body : JSON.stringify(body), { status, headers })

const stubFetch = (res = new Response('{}', { status: 200 })) => {
  const fetchMock = vi.fn().mockResolvedValue(res)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

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

describe('sessão por cookie', () => {
  it('apiRequest manda o cookie (credentials: include) e nenhum Authorization', async () => {
    const fetchMock = stubFetch()
    await apiRequest('/menu')

    const init = fetchMock.mock.calls[0][1]
    expect(init.credentials).toBe('include')
    expect(Object.keys(init.headers)).not.toContain('Authorization')
  })

  it('login deixa o navegador guardar o cookie e não devolve o token', async () => {
    const fetchMock = stubFetch(new Response('{"access_token":"segredo","token_type":"bearer"}', { status: 200 }))

    await expect(authService.login({ email: 'a@x.com', password: 'senha' })).resolves.toBeUndefined()
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
  })

  it('login recusado mostra o detail do backend', async () => {
    stubFetch(new Response('{"detail":"Incorrect email or password"}', { status: 401 }))
    await expect(authService.login({ email: 'a@x.com', password: 'x' })).rejects.toThrow('Incorrect email or password')
  })

  it('login com 422 mostra a mensagem do campo (detail[0].msg), não [object Object]', async () => {
    stubFetch(
      response(422, {
        detail: [{ type: 'string_too_short', loc: ['body', 'password'], msg: 'Field required', input: null }],
      })
    )
    const error = await authService.login({ email: 'a@x.com', password: '' }).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(Error)
    expect((error as Error).message).toBe('Field required')
  })

  it('login com 401 não derruba a sessão: é senha errada, não cookie vencido', async () => {
    const fetchMock = stubFetch(response(401, { detail: 'Incorrect email or password' }))

    await expect(authService.login({ email: 'a@x.com', password: 'x' })).rejects.toThrow('Incorrect email or password')
    // `apiRequest` chamaria `endSession()` num 401, que faz um segundo fetch (logout no backend).
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/api\/v1\/auth\/login$/)
  })

  it('login sem rede (TypeError do fetch) mostra mensagem em português, não "Failed to fetch"', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(authService.login({ email: 'a@x.com', password: 'x' })).rejects.toThrow(
      'Sem conexão com o servidor. Tente de novo.'
    )
  })

  it('logout pede ao backend para apagar o cookie', async () => {
    const fetchMock = stubFetch(new Response(null, { status: 204 }))
    await authService.logout()

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/api\/v1\/auth\/logout$/)
    expect(init).toMatchObject({ method: 'POST', credentials: 'include' })
  })

  it('logout recusado pelo backend (403 por CORS_ORIGINS) vira erro: o cookie segue valendo', async () => {
    stubFetch(new Response('{"detail":"Origin not allowed"}', { status: 403 }))
    await expect(authService.logout()).rejects.toThrow('Origin not allowed')
  })

  it('logout com erro 5xx também vira erro', async () => {
    stubFetch(new Response('', { status: 502 }))
    await expect(authService.logout()).rejects.toThrow('Erro ao encerrar a sessão')
  })
})
