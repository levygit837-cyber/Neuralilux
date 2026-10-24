import { describe, expect, it } from 'vitest'
import {
  mapConversation,
  mapMessage,
  mapMessageStatus,
  mapRealtimeMessage,
  parseServerDate,
  type ConversationResponse,
  type MessageResponse,
} from '@/services/chatMapper'

const rawMessage = (over: Partial<MessageResponse> = {}): MessageResponse =>
  ({
    id: 'db-1',
    message_id: 'evo-1',
    message_type: 'text',
    content: 'oi',
    caption: null,
    timestamp: '2026-10-24T10:00:00',
    is_from_me: false,
    status: 'read',
    ...over,
  }) as MessageResponse

describe('parseServerDate', () => {
  it('lê data sem fuso como UTC', () => {
    expect(parseServerDate('2026-10-24T10:00:00').toISOString()).toBe('2026-10-24T10:00:00.000Z')
  })

  it('respeita fuso explícito', () => {
    expect(parseServerDate('2026-10-24T10:00:00Z').toISOString()).toBe('2026-10-24T10:00:00.000Z')
    expect(parseServerDate('2026-10-24T10:00:00-03:00').toISOString()).toBe('2026-10-24T13:00:00.000Z')
  })
})

describe('mapMessageStatus', () => {
  it('mapeia os status conhecidos e reduz o resto a pending', () => {
    expect(mapMessageStatus('read')).toBe('read')
    expect(mapMessageStatus('delivered')).toBe('delivered')
    expect(mapMessageStatus('sent')).toBe('sent')
    expect(mapMessageStatus('failed')).toBe('pending')
    expect(mapMessageStatus(undefined)).toBe('pending')
  })
})

describe('mapMessage', () => {
  it('usa o message_id da Evolution como id e cai no id do banco', () => {
    expect(mapMessage(rawMessage(), 'c1', 'Ana').id).toBe('evo-1')
    expect(mapMessage(rawMessage({ message_id: null }), 'c1', 'Ana').id).toBe('db-1')
  })

  it('texto: conteúdo, depois legenda, depois placeholder da mídia', () => {
    expect(mapMessage(rawMessage({ content: '  ola  ' }), 'c1', 'Ana').content).toBe('ola')
    expect(mapMessage(rawMessage({ content: ' ', caption: 'foto linda' }), 'c1', 'Ana').content).toBe('foto linda')
    expect(mapMessage(rawMessage({ content: null, message_type: 'image' }), 'c1', 'Ana').content).toBe('[Imagem]')
    expect(mapMessage(rawMessage({ content: null, message_type: 'zzz' }), 'c1', 'Ana').content).toBe(
      '[Mensagem sem texto]'
    )
  })

  it('remetente: contato no individual, sender_name no grupo, nenhum se enviada por nós', () => {
    expect(mapMessage(rawMessage(), 'c1', 'Ana').sender).toEqual({ name: 'Ana' })
    expect(mapMessage(rawMessage({ sender_name: ' Beto ' }), 'c1', 'Grupo', true).sender).toEqual({ name: 'Beto' })
    expect(mapMessage(rawMessage({ sender_name: null }), 'c1', 'Grupo', true).sender).toEqual({ name: 'Participante' })
    const mine = mapMessage(rawMessage({ is_from_me: true }), 'c1', 'Ana')
    expect(mine.sender).toBeUndefined()
    expect(mine.isOutgoing).toBe(true)
  })
})

describe('mapRealtimeMessage', () => {
  it('gera id estável quando o evento não traz id', () => {
    const message = mapRealtimeMessage(
      { conversation_id: 'c1', content: 'oi', timestamp: '2026-10-24T10:00:00', is_outgoing: false } as never,
      'c1'
    )
    expect(message.id).toBe('rt_c1_2026-10-24T10:00:00')
    expect(message.conversationId).toBe('c1')
  })
})

describe('mapConversation', () => {
  const raw = (over: Partial<ConversationResponse> = {}): ConversationResponse =>
    ({ id: 'c1', remote_jid: '5511999990000@s.whatsapp.net', ...over }) as ConversationResponse

  it('nome: contato, push_name, telefone, depois o número do JID', () => {
    expect(mapConversation(raw({ contact: { name: ' Ana ' } as never })).name).toBe('Ana')
    expect(mapConversation(raw({ contact: { name: ' ', push_name: 'Aninha' } as never })).name).toBe('Aninha')
    expect(mapConversation(raw({ contact: { phone_number: '+55 11' } as never })).name).toBe('+55 11')
    expect(mapConversation(raw()).name).toBe('5511999990000')
  })

  it('aplica padrões de não lidas, grupo e handoff', () => {
    const conversation = mapConversation(raw())
    expect(conversation.unreadCount).toBe(0)
    expect(conversation.conversationType).toBe('individual')
    expect(conversation.humanHandoff).toBe(false)
    expect(conversation.handoffAssignedTo).toBeNull()
    expect(mapConversation(raw({ is_group: true })).conversationType).toBe('group')
  })

  it('last_message_at sem fuso vira ISO em UTC', () => {
    expect(mapConversation(raw({ last_message_at: '2026-10-24T10:00:00' })).lastMessageAt).toBe(
      '2026-10-24T10:00:00.000Z'
    )
  })
})
