import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EventEmitter } from 'node:events'

class FakeSocket extends EventEmitter {
  connected = false
  active = true
  emitted: Array<{ event: string; data: unknown }> = []
  disconnect = vi.fn(() => {
    this.connected = false
    this.active = false
  })
  connect = vi.fn(() => {
    this.active = true
  })
  // `emit` do EventEmitter dispara ouvintes; o do cliente envia ao servidor. O fake guarda o que foi enviado.
  send(event: string, data: unknown, ack?: (response: { ok: boolean }) => void) {
    this.emitted.push({ event, data })
    ack?.({ ok: true })
  }
  /** Simula o servidor: o handshake vingou. */
  serverConnects() {
    this.connected = true
    super.emit('connect')
  }
}

const mocks = vi.hoisted(() => ({
  sockets: [] as unknown[],
  endSession: vi.fn(),
  invalidateQueries: vi.fn(),
}))

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => {
    const socket = new FakeSocket()
    // O serviço chama `socket.emit(evento, dados, ack)`: no fake, isso é envio ao servidor.
    ;(socket as unknown as { emit: unknown }).emit = (event: string, data: unknown, ack?: never) =>
      socket.send(event, data, ack)
    ;(socket as unknown as { on: unknown }).on = EventEmitter.prototype.on.bind(socket)
    mocks.sockets.push(socket)
    return socket
  }),
}))
vi.mock('@/services/http', () => ({ endSession: mocks.endSession }))
vi.mock('@/lib/queryClient', () => ({ getQueryClient: () => ({ invalidateQueries: mocks.invalidateQueries }) }))

import { io } from 'socket.io-client'
import type { SocketNotice } from '@/services/socketService'
import { THINKING_CLEAR_DELAY_MS } from '@/lib/thinkingTimers'
import type { Conversation } from '@/types/chat'

// O serviço é um singleton com estado (socket, salas): cada teste carrega uma cópia nova dele e do store.
let socketService: typeof import('@/services/socketService').socketService
let useChatStore: typeof import('@/stores/useChatStore').useChatStore
let timers: typeof import('@/lib/thinkingTimers')

const current = () => mocks.sockets.at(-1) as FakeSocket
/** Eventos do servidor para o cliente: o `emit` do fake virou envio, então o servidor usa `trigger`. */
const trigger = (event: string, payload?: unknown) => EventEmitter.prototype.emit.call(current(), event, payload)
const sent = (event: string) => current().emitted.filter((item) => item.event === event).map((item) => item.data)

describe('socketService', () => {
  beforeEach(async () => {
    vi.useFakeTimers()
    vi.resetModules()
    mocks.sockets.length = 0
    vi.mocked(io).mockClear()
    mocks.endSession.mockClear()
    mocks.invalidateQueries.mockClear()
    ;({ socketService } = await import('@/services/socketService'))
    ;({ useChatStore } = await import('@/stores/useChatStore'))
    timers = await import('@/lib/thinkingTimers')
    socketService.connect()
  })

  afterEach(() => {
    socketService.disconnect()
    timers.cancelAllThinkingClears()
    vi.useRealTimers()
  })

  it('autentica pelo cookie no handshake e reconecta sem limite, com intervalo teto', () => {
    const options = (vi.mocked(io).mock.calls[0] as unknown as [string, Record<string, unknown>])[1]
    expect(options.withCredentials).toBe(true)
    expect(options).not.toHaveProperty('auth')
    expect(options.reconnection).toBe(true)
    expect(options.reconnectionAttempts).toBe(Infinity)
    expect(options.reconnectionDelayMax).toBeGreaterThan(options.reconnectionDelay as number)
  })

  it('reconectar refaz o subscribe da Instance e o join da Conversation, e invalida as queries', () => {
    socketService.subscribeToInstance('i1')
    socketService.joinConversation('i1', 'c1')
    current().serverConnects()
    expect(sent('subscribe_instance')).toEqual([{ instanceId: 'i1' }])
    expect(sent('join_conversation')).toEqual([{ instanceId: 'i1', conversationId: 'c1' }])
    expect(mocks.invalidateQueries).not.toHaveBeenCalled()

    // Queda e volta: as salas do servidor sumiram.
    current().connected = false
    trigger('disconnect', 'transport close')
    const notices: SocketNotice[] = []
    socketService.subscribe((notice) => notices.push(notice))
    current().serverConnects()

    expect(sent('subscribe_instance')).toHaveLength(2)
    expect(sent('join_conversation')).toHaveLength(2)
    expect(mocks.invalidateQueries).toHaveBeenCalled()
    expect(notices).toContainEqual({ type: 'reconnected' })
  })

  it('duas telas na mesma Instance: sair de uma não tira a sala da outra', () => {
    current().serverConnects()
    socketService.subscribeToInstance('i1')
    socketService.subscribeToInstance('i1')
    expect(sent('subscribe_instance')).toHaveLength(1)

    socketService.leaveInstance('i1')
    expect(sent('leave_instance')).toHaveLength(0)
    socketService.leaveInstance('i1')
    expect(sent('leave_instance')).toEqual([{ instanceId: 'i1' }])
  })

  it('connect_error de autenticação encerra a sessão e para de reconectar', () => {
    trigger('connect_error', new Error('unauthorized'))

    expect(mocks.endSession).toHaveBeenCalledTimes(1)
    expect(current().disconnect).toHaveBeenCalled()
  })

  it('connect_error de rede avisa a UI e continua tentando, sem encerrar a sessão', () => {
    trigger('connect_error', new Error('xhr poll error'))

    expect(mocks.endSession).not.toHaveBeenCalled()
    expect(current().disconnect).not.toHaveBeenCalled()
    expect(socketService.getState()).toEqual({ connected: false, degraded: true })

    current().serverConnects()
    expect(socketService.getState()).toEqual({ connected: true, degraded: false })
  })

  it('desligar pelo provider não conta como queda', () => {
    current().serverConnects()
    socketService.disconnect()
    trigger('disconnect', 'io client disconnect')

    expect(socketService.getState()).toEqual({ connected: false, degraded: false })
  })

  describe('Thinking por rodada', () => {
    const conversation = { id: 'c1', remoteJid: 'x@s.whatsapp.net', name: 'Ana' } as Conversation
    const thinking = (event: 'thinking_start' | 'thinking_end', data?: object) =>
      trigger('thinking_event', { instance_id: 'i1', conversation_id: 'c1', event, data })
    const state = () => useChatStore.getState().thinkingEvents.c1?.state

    beforeEach(() => useChatStore.getState().setConversations([conversation], 1))

    it('o fim da rodada apaga o Thinking depois do prazo', () => {
      thinking('thinking_start')
      thinking('thinking_end', { summary: 'ok' })
      expect(state()).toBe('collapsed')

      vi.advanceTimersByTime(THINKING_CLEAR_DELAY_MS)
      expect(state()).toBeUndefined()
    })

    it('rodada nova menos de 5 s depois do thinking_end mantém o Thinking', () => {
      thinking('thinking_start')
      thinking('thinking_end')
      vi.advanceTimersByTime(THINKING_CLEAR_DELAY_MS - 1000)

      thinking('thinking_start')
      vi.advanceTimersByTime(2000) // passa do prazo da rodada anterior

      expect(state()).toBe('indicator')
    })

    it('o fim da segunda rodada tem o próprio prazo', () => {
      thinking('thinking_start')
      thinking('thinking_end')
      vi.advanceTimersByTime(3000)
      thinking('thinking_start')
      thinking('thinking_end')

      vi.advanceTimersByTime(THINKING_CLEAR_DELAY_MS - 1)
      expect(state()).toBe('collapsed')
      vi.advanceTimersByTime(1)
      expect(state()).toBeUndefined()
    })
  })
})
