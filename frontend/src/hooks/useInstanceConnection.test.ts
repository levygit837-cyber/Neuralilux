// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { useQuery } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useInstanceConnection } from '@/hooks/useInstanceConnection'
import { queryKeys } from '@/lib/queryKeys'
import { instanceService, type Instance } from '@/services/instanceService'
import { socketService, type SocketNotice } from '@/services/socketService'
import { useAuthStore } from '@/stores/useAuthStore'
import { queryWrapper } from '@/test/queryWrapper'

vi.mock('@/services/instanceService', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/services/instanceService')>()),
  instanceService: { list: vi.fn(), getStatus: vi.fn(), connect: vi.fn(), logout: vi.fn() },
}))
vi.mock('@/services/socketService', () => ({
  socketService: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    subscribe: vi.fn(),
    subscribeToInstance: vi.fn(),
    leaveInstance: vi.fn(),
  },
}))

const instance = (status: Instance['status']): Instance => ({
  id: 'i1',
  name: 'loja',
  status,
  agentEnabled: false,
  profileName: '',
  profilePicUrl: '',
})

describe('useInstanceConnection: lista de Instances em cache', () => {
  let emit: (notice: SocketNotice) => void

  beforeEach(() => {
    useAuthStore.setState({ isAuthenticated: true, hasHydrated: true })
    vi.mocked(socketService.subscribe).mockImplementation((listener) => {
      emit = listener as typeof emit
      return () => undefined
    })
    vi.mocked(instanceService.getStatus).mockResolvedValue('connected')
  })

  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
    useAuthStore.setState({ isAuthenticated: false, hasHydrated: false })
  })

  // Uma tela que mostra a lista (Configurações, Instâncias) e a tela do QR no mesmo cliente.
  function setup() {
    const { client, Wrapper } = queryWrapper()
    const view = renderHook(
      () => ({
        list: useQuery({ queryKey: queryKeys.instances, queryFn: instanceService.list, staleTime: 60_000 }),
        connection: useInstanceConnection('loja'),
      }),
      { wrapper: Wrapper }
    )
    return { client, ...view }
  }

  // Espera a tela do QR e a lista concordarem (a busca inicial já terminou) antes de provocar a mudança.
  async function settled(result: { current: ReturnType<typeof setup>['result']['current'] }) {
    await waitFor(() => expect(result.current.connection.status).toBe('connected'))
    await waitFor(() => expect(result.current.list.data?.[0].status).toBe('connected'))
    await waitFor(() => expect(result.current.list.isFetching).toBe(false))
  }

  it('o status que chega pelo socket refaz a lista, que mostra o valor novo', async () => {
    vi.mocked(instanceService.list).mockResolvedValue([instance('connected')])
    const { result } = setup()
    await settled(result)

    vi.mocked(instanceService.list).mockResolvedValue([instance('disconnected')])
    act(() => emit({ type: 'instance_status', status: 'disconnected' }))

    await waitFor(() => expect(result.current.list.data?.[0].status).toBe('disconnected'))
  })

  it('o mesmo status repetido pelo socket não refaz a lista', async () => {
    vi.mocked(instanceService.list).mockResolvedValue([instance('connected')])
    const { result } = setup()
    await settled(result)
    const before = vi.mocked(instanceService.list).mock.calls.length

    act(() => emit({ type: 'instance_status', status: 'connected' }))
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(instanceService.list).toHaveBeenCalledTimes(before)
  })

  it('desconectar refaz a lista', async () => {
    vi.mocked(instanceService.list).mockResolvedValue([instance('connected')])
    vi.mocked(instanceService.logout).mockResolvedValue(undefined)
    const { result } = setup()
    await settled(result)
    vi.mocked(instanceService.list).mockResolvedValue([instance('disconnected')])

    await act(async () => {
      await result.current.connection.disconnect()
    })

    await waitFor(() => expect(result.current.list.data?.[0].status).toBe('disconnected'))
  })

  it('desconectar refaz a lista mesmo quando o status local já era desconectado', async () => {
    // A leitura inicial falha: o hook fica em "desconectado" e nunca recebe um status novo.
    vi.mocked(instanceService.getStatus).mockRejectedValue(new Error('sem resposta'))
    vi.mocked(instanceService.logout).mockResolvedValue(undefined)
    vi.mocked(instanceService.list).mockResolvedValue([instance('connected')])
    const { result } = setup()
    await waitFor(() => expect(result.current.connection.error).toBe('sem resposta'))
    await waitFor(() => expect(result.current.list.data?.[0].status).toBe('connected'))
    await waitFor(() => expect(result.current.list.isFetching).toBe(false))
    vi.mocked(instanceService.list).mockResolvedValue([instance('disconnected')])

    await act(async () => {
      await result.current.connection.disconnect()
    })

    await waitFor(() => expect(result.current.list.data?.[0].status).toBe('disconnected'))
  })

  it('conectar (QR pedido) refaz a lista', async () => {
    vi.mocked(instanceService.getStatus).mockResolvedValue('connected')
    vi.mocked(instanceService.connect).mockResolvedValue({ qrCode: 'qr', status: 'connecting' })
    vi.mocked(instanceService.list).mockResolvedValue([instance('connected')])
    const { result } = setup()
    await settled(result)
    vi.mocked(instanceService.list).mockResolvedValue([instance('connecting')])

    await act(async () => {
      await result.current.connection.connect()
    })

    await waitFor(() => expect(result.current.list.data?.[0].status).toBe('connecting'))
  })
})
