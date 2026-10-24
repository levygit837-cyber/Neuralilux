import { describe, expect, it } from 'vitest'
import { errorFromResponse } from '@/services/http'

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('errorFromResponse', () => {
  it('usa o detail em texto como mensagem', async () => {
    const error = await errorFromResponse(json(409, { detail: 'Já existe' }))
    expect(error.status).toBe(409)
    expect(error.message).toBe('Já existe')
    expect(error.fieldErrors).toEqual({})
  })

  it('num 422 junta as mensagens e indexa a primeira por campo', async () => {
    const error = await errorFromResponse(
      json(422, {
        detail: [
          { loc: ['body', 'name'], msg: 'Value error, Nome obrigatório' },
          { loc: ['body', 'name'], msg: 'Nome curto demais' },
          { loc: ['body', 'phone'], msg: 'Telefone inválido' },
        ],
      })
    )
    expect(error.status).toBe(422)
    expect(error.message).toBe('Nome obrigatório; Nome curto demais; Telefone inválido')
    expect(error.fieldErrors).toEqual({ name: 'Nome obrigatório', phone: 'Telefone inválido' })
  })

  it('ignora itens sem msg e campos não textuais', async () => {
    const error = await errorFromResponse(
      json(422, { detail: [{ loc: ['body', 0], msg: 'Item ruim' }, { loc: ['body', 'x'] }] }),
      'fallback'
    )
    expect(error.message).toBe('Item ruim')
    expect(error.fieldErrors).toEqual({})
  })

  it('cai no fallback quando o corpo não é JSON', async () => {
    const error = await errorFromResponse(new Response('<html>', { status: 502 }), 'Falha ao carregar')
    expect(error.message).toBe('Falha ao carregar')
    expect(error.status).toBe(502)
  })

  it('sem fallback usa o status', async () => {
    const error = await errorFromResponse(new Response('', { status: 500 }))
    expect(error.message).toBe('Erro 500')
  })
})
