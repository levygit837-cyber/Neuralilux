// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatData } from '@/hooks/useChatData'
import { chatService, type ConversationPage } from '@/services/chatService'
import { useChatStore } from '@/stores/useChatStore'
import type { Conversation } from '@/types/chat'

vi.mock('@/services/chatService', () => ({
  chatService: {
    getConversations: vi.fn(),
    getCounts: vi.fn(),
    getMessages: vi.fn(),
    markRead: vi.fn(),
    sendMessage: vi.fn(),
    syncHistory: vi.fn(),
  },
}))
vi.mock('@/services/socketService', () => ({ socketService: { subscribe: () => () => undefined } }))

const conversation = (id: string): Conversation =>
  ({ id, remoteJid: `${id}@s.whatsapp.net`, name: id, lastMessage: '', timestamp: '', unreadCount: 0 }) as Conversation

const page = (...ids: string[]): ConversationPage => ({ conversations: ids.map(conversation), total: ids.length })

const getConversations = vi.mocked(chatService.getConversations)
const listIds = () => useChatStore.getState().conversations.map((c) => c.id)

describe('useChatData: respostas fora de ordem', () => {
  beforeEach(() => {
    vi.mocked(chatService.getCounts).mockResolvedValue({
      all: 0,
      unread: 0,
      groups: 0,
      ai: 0,
      human: 0,
      unreadMessages: 0,
    })
    vi.mocked(chatService.getMessages).mockResolvedValue([])
    useChatStore.getState().reset()
  })
  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
  })

  it('a lista da Instance anterior, que chega depois, não sobrescreve a nova', async () => {
    const instanceA = Promise.withResolvers<ConversationPage>()
    const instanceB = Promise.withResolvers<ConversationPage>()
    getConversations.mockReturnValueOnce(instanceA.promise).mockReturnValueOnce(instanceB.promise)

    const { rerender } = renderHook(({ id }) => useChatData(id, true), { initialProps: { id: 'A' } })
    rerender({ id: 'B' })

    await act(async () => instanceB.resolve(page('b1')))
    await waitFor(() => expect(listIds()).toEqual(['b1']))
    await act(async () => instanceA.resolve(page('a1')))

    expect(listIds()).toEqual(['b1'])
    expect(useChatStore.getState().isLoadingConversations).toBe(false)
  })

  it('a carga antiga do mesmo filtro, que chega depois da nova, é descartada', async () => {
    const before = Promise.withResolvers<ConversationPage>()
    const after = Promise.withResolvers<ConversationPage>()
    getConversations.mockReturnValueOnce(before.promise).mockReturnValueOnce(after.promise)

    renderHook(() => useChatData('A', true))
    act(() => useChatStore.getState().setCategory('unread'))

    await act(async () => after.resolve(page('unread-1')))
    await waitFor(() => expect(listIds()).toEqual(['unread-1']))
    await act(async () => before.resolve(page('all-1', 'all-2')))

    expect(listIds()).toEqual(['unread-1'])
  })

  it('"Carregar mais" de uma busca anterior não entra na lista da busca atual', async () => {
    const more = Promise.withResolvers<ConversationPage>()
    getConversations
      .mockResolvedValueOnce({ conversations: [conversation('a1')], total: 3 })
      .mockReturnValueOnce(more.promise)
      .mockResolvedValueOnce(page('found-1'))

    const { result } = renderHook(() => useChatData('A', true))
    await waitFor(() => expect(listIds()).toEqual(['a1']))

    act(() => {
      void result.current.loadMoreConversations()
    })
    act(() => useChatStore.getState().setSearch('maria'))
    await waitFor(() => expect(listIds()).toEqual(['found-1']))
    await act(async () => more.resolve(page('stale-1')))

    expect(listIds()).toEqual(['found-1'])
    expect(useChatStore.getState().isLoadingMore).toBe(false)
  })
})
