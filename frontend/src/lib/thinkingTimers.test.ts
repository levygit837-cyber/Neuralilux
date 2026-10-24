import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  THINKING_CLEAR_DELAY_MS,
  cancelAllThinkingClears,
  cancelThinkingClear,
  scheduleThinkingClear,
} from '@/lib/thinkingTimers'

describe('thinkingTimers', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    cancelAllThinkingClears()
    vi.useRealTimers()
  })

  it('dispara depois do prazo', () => {
    const clear = vi.fn()
    scheduleThinkingClear('c1', clear)
    vi.advanceTimersByTime(THINKING_CLEAR_DELAY_MS - 1)
    expect(clear).not.toHaveBeenCalled()
    vi.advanceTimersByTime(1)
    expect(clear).toHaveBeenCalledTimes(1)
  })

  it('agendar de novo na mesma Conversation cancela o timer anterior', () => {
    const first = vi.fn()
    const second = vi.fn()
    scheduleThinkingClear('c1', first)
    vi.advanceTimersByTime(3000)
    scheduleThinkingClear('c1', second)
    vi.advanceTimersByTime(THINKING_CLEAR_DELAY_MS)
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('cancelar um não toca nos das outras Conversations', () => {
    const c1 = vi.fn()
    const c2 = vi.fn()
    scheduleThinkingClear('c1', c1)
    scheduleThinkingClear('c2', c2)
    cancelThinkingClear('c1')
    vi.advanceTimersByTime(THINKING_CLEAR_DELAY_MS)
    expect(c1).not.toHaveBeenCalled()
    expect(c2).toHaveBeenCalledTimes(1)
  })

  it('cancelAll cancela todos', () => {
    const fired = vi.fn()
    scheduleThinkingClear('c1', fired)
    scheduleThinkingClear('c2', fired)
    cancelAllThinkingClears()
    vi.advanceTimersByTime(THINKING_CLEAR_DELAY_MS)
    expect(fired).not.toHaveBeenCalled()
  })
})
