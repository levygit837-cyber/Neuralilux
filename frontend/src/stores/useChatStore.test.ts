import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useChatStore } from '@/stores/useChatStore'
import type { Conversation, Message } from '@/types/chat'

const conversation = (id: string, lastMessageAt: string, over: Partial<Conversation> = {}): Conversation =>
  ({ id, remoteJid: `${id}@s.whatsapp.net`, name: id, lastMessage: '', timestamp: '', lastMessageAt, unreadCount: 0, ...over }) as Conversation

const message = (id: string, conversationId = 'c1', over: Partial<Message> = {}): Message => ({
  id,
  conversationId,
  content: id,
  timestamp: new Date(0),
  isOutgoing: true,
  status: 'sending',
  messageType: 'text',
  ...over,
})

const store = () => useChatStore.getState()

/** `setTimeout` do DOM devolve number; o store guarda o tipo do Node. */
const schedule = (fn: () => void) => setTimeout(fn, 1000) as unknown as ReturnType<typeof setTimeout>

describe('useChatStore', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    store().reset()
  })
  afterEach(() => {
    store().reset()
    vi.useRealTimers()
  })

  describe('Messages', () => {
    it('addMessage ignora id repetido', () => {
      store().addMessage(message('m1'))
      store().addMessage(message('m1'))
      expect(store().messages.c1).toHaveLength(1)
    })

    it('updateMessage troca a temporária pela confirmada', () => {
      store().addMessage(message('temp_1'))
      store().updateMessage('temp_1', message('evo-1', 'c1', { status: 'sent' }))
      expect(store().messages.c1.map((m) => m.id)).toEqual(['evo-1'])
    })

    it('updateMessage não duplica quando o evento realtime chegou antes do POST', () => {
      store().addMessage(message('temp_1'))
      store().addMessage(message('evo-1'))
      store().updateMessage('temp_1', message('evo-1', 'c1', { status: 'sent' }))
      expect(store().messages.c1.map((m) => m.id)).toEqual(['evo-1'])
    })

    it('updateMessageStatus muda só a Message pedida', () => {
      store().setMessages('c1', [message('a'), message('b')])
      store().updateMessageStatus('b', 'failed')
      expect(store().messages.c1.map((m) => m.status)).toEqual(['sending', 'failed'])
    })
  })

  describe('Conversations', () => {
    it('ordena da mais recente para a mais antiga', () => {
      store().setConversations(
        [conversation('old', '2026-10-01T00:00:00Z'), conversation('new', '2026-10-20T00:00:00Z')],
        2
      )
      expect(store().conversations.map((c) => c.id)).toEqual(['new', 'old'])
    })

    it('appendConversations não repete ids já carregados', () => {
      store().setConversations([conversation('a', '2026-10-02T00:00:00Z')], 3)
      store().appendConversations(
        [conversation('a', '2026-10-02T00:00:00Z'), conversation('b', '2026-10-01T00:00:00Z')],
        3
      )
      expect(store().conversations.map((c) => c.id)).toEqual(['a', 'b'])
    })

    it('a aberta que o filtro tirou da lista fica fixada; ao voltar, a da lista vale', () => {
      const open = conversation('open', '2026-10-01T00:00:00Z')
      store().setConversations([open], 1)
      store().setActiveConversation('open')
      store().setConversations([conversation('other', '2026-10-02T00:00:00Z')], 1)
      expect(store().pinnedConversation?.id).toBe('open')
      store().setConversations([open], 1)
      expect(store().pinnedConversation).toBeNull()
    })

    it('só a escolha do usuário é explícita', () => {
      store().setActiveConversation('a')
      expect(store().isActiveExplicit).toBe(true)
      store().autoSelectConversation('b')
      expect(store().isActiveExplicit).toBe(false)
    })

    it('resetUnreadCount zera também a cópia fixada', () => {
      const open = conversation('open', '2026-10-01T00:00:00Z', { unreadCount: 4 })
      store().setConversations([open], 1)
      store().setActiveConversation('open')
      store().setConversations([], 0)
      store().resetUnreadCount('open')
      expect(store().pinnedConversation?.unreadCount).toBe(0)
    })

    it('setConversationHandoff limpa o responsável ao devolver ao Agent', () => {
      store().setConversations([conversation('a', '2026-10-01T00:00:00Z')], 1)
      store().setConversationHandoff('a', true, 'user-1')
      expect(store().conversations[0]).toMatchObject({ humanHandoff: true, handoffAssignedTo: 'user-1' })
      store().setConversationHandoff('a', false, 'user-1')
      expect(store().conversations[0]).toMatchObject({ humanHandoff: false, handoffAssignedTo: null })
    })
  })

  describe('Thinking', () => {
    it('indicator zera os tokens e marca o início', () => {
      store().setThinkingState('c1', 'indicator')
      expect(store().thinkingEvents.c1.tokens).toEqual([])
      expect(store().thinkingEvents.c1.startedAt).toBeInstanceOf(Date)
    })

    it('tokens só entram enquanto o Thinking está ativo', () => {
      store().appendThinkingToken('c1', 'x')
      expect(store().thinkingEvents.c1).toBeUndefined()

      store().setThinkingState('c1', 'indicator')
      store().appendThinkingToken('c1', 'a')
      store().appendThinkingToken('c1', 'b')
      expect(store().thinkingEvents.c1).toMatchObject({ state: 'streaming', tokens: ['a', 'b'] })

      store().collapseThinking('c1')
      store().appendThinkingToken('c1', 'c')
      expect(store().thinkingEvents.c1.tokens).toEqual(['a', 'b'])
    })

    it('collapse resume pelos tokens quando não há resumo', () => {
      store().setThinkingState('c1', 'indicator')
      store().appendThinkingToken('c1', 'pensando')
      store().appendThinkingToken('c1', 'alto')
      store().collapseThinking('c1')
      expect(store().thinkingEvents.c1).toMatchObject({ state: 'collapsed', summary: 'pensando alto' })
      store().collapseThinking('c1', 'resumo dado')
      expect(store().thinkingEvents.c1.summary).toBe('resumo dado')
    })

    it('clearThinking remove o evento e o timer da Conversation, sem tocar nas outras', () => {
      store().setThinkingState('c1', 'indicator')
      store().setThinkingState('c2', 'indicator')
      useChatStore.setState({ thinkingClearTimers: { c1: schedule(() => undefined), c2: null } })
      store().clearThinking('c1')
      expect(store().thinkingEvents.c1).toBeUndefined()
      expect(store().thinkingEvents.c2).toBeDefined()
      expect(Object.keys(store().thinkingClearTimers)).toEqual(['c2'])
    })

    it('cancelClearTimer impede o disparo do timer agendado', () => {
      const fired = vi.fn()
      useChatStore.setState({ thinkingClearTimers: { c1: schedule(fired) } })
      store().cancelClearTimer('c1')
      vi.advanceTimersByTime(2000)
      expect(fired).not.toHaveBeenCalled()
      expect(store().thinkingClearTimers.c1).toBeUndefined()
    })

    it('reset cancela todos os timers pendentes', () => {
      const fired = vi.fn()
      useChatStore.setState({
        thinkingClearTimers: { c1: schedule(fired), c2: schedule(fired) },
      })
      store().reset()
      vi.advanceTimersByTime(2000)
      expect(fired).not.toHaveBeenCalled()
      expect(store().thinkingClearTimers).toEqual({})
    })
  })
})
