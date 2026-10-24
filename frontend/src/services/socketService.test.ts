import { beforeEach, describe, expect, it, vi } from 'vitest'

const io = vi.hoisted(() => vi.fn(() => ({ on: vi.fn(), emit: vi.fn(), disconnect: vi.fn(), connected: false })))
vi.mock('socket.io-client', () => ({ io }))

import { socketService } from '@/services/socketService'

describe('socketService.connect', () => {
  beforeEach(() => io.mockClear())

  it('autentica pelo cookie no handshake: withCredentials e nenhum token em auth', () => {
    socketService.connect()

    const options = (io.mock.calls[0] as unknown as [string, Record<string, unknown>])[1]
    expect(options.withCredentials).toBe(true)
    expect(options).not.toHaveProperty('auth')
  })
})
