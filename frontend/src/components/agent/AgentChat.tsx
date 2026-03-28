'use client'

import { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react'
import { Clock3, MoreVertical, Plus, Search } from 'lucide-react'
import { AgentMessage } from './AgentMessage'
import { AgentInputBar } from './AgentInputBar'
import { buildThinkingSummary } from './buildThinkingSummary'
import type {
  AgentMessage as AgentMessageType,
  AgentToolEvent,
  AgentSessionMessage,
  AgentSessionSummary,
} from '@/types/agent'
import { agentService } from '@/services/agentService'
import { socketService } from '@/services/socketService'
import { useAuthStore } from '@/stores/useAuthStore'

const AGENT_SESSION_STORAGE_KEY = 'neuralilux-agent-session-id'
const MIN_THINKING_INDICATOR_MS = 0
const MIN_THINKING_STREAMING_MS = 0
const THINKING_DRAIN_BATCH_SIZE = 20
const THINKING_DRAIN_INTERVAL_MS = 8
const THINKING_END_GRACE_MS = 800
const AUTO_SCROLL_EPSILON_PX = 1
const AUTO_SCROLL_MIN_STEP_PX = 6
const AUTO_SCROLL_MAX_STEP_PX = 40
const AUTO_SCROLL_LERP = 0.32
const BULK_SCROLL_SYNC_THRESHOLD = 6
const TOOL_PREVIEW_MAX_LENGTH = 240

type ActiveThinkingRuntime = {
  id: string
  startedAt: number
  stage: 'indicator' | 'streaming'
  queuedTokens: string[]
  sawThinkingTokens: boolean
  hasEnded: boolean
  endSummary?: string
  fallbackContent?: string
  streamingStartedAt?: number
  indicatorTimer: ReturnType<typeof setTimeout> | null
  drainTimer: ReturnType<typeof setTimeout> | null
  finalizeTimer: ReturnType<typeof setTimeout> | null
  forceFinalizeTimer: ReturnType<typeof setTimeout> | null
}

function createWelcomeMessage(): AgentMessageType {
  return {
    id: 'welcome-message',
    content: 'Olá! Sou o assistente da Neuralilux. Como posso ajudá-lo hoje?',
    timestamp: new Date(),
    isAgent: true,
  }
}

function normalizeToolPhase(value?: string): AgentToolEvent['phase'] {
  if (value === 'waiting_input' || value === 'started' || value === 'failed') {
    return value
  }
  return 'completed'
}

function buildToolPreview(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return undefined
  }

  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  const normalized = text.trim()
  if (!normalized) {
    return undefined
  }

  if (normalized.length <= TOOL_PREVIEW_MAX_LENGTH) {
    return normalized
  }

  return `${normalized.slice(0, TOOL_PREVIEW_MAX_LENGTH - 1)}…`
}

function parseToolOutput(value?: string | null): unknown {
  if (!value) {
    return null
  }

  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function buildToolMessage(
  toolEvent: AgentToolEvent,
  id: string,
  timestamp?: string | Date
): AgentMessageType {
  const parsedTimestamp =
    timestamp instanceof Date
      ? timestamp
      : typeof timestamp === 'string' && timestamp
        ? new Date(timestamp)
        : new Date(toolEvent.finishedAt || toolEvent.startedAt || toolEvent.persistedAt || Date.now())

  return {
    id,
    content: '',
    timestamp: Number.isNaN(parsedTimestamp.getTime()) ? new Date() : parsedTimestamp,
    isAgent: true,
    blockType: 'tool_result',
    toolEvent,
  }
}

function buildToolMessageFromHistory(item: AgentSessionMessage): AgentMessageType | null {
  if (item.role !== 'tool' || !item.tool_name) {
    return null
  }

  const metadata = item.metadata || {}
  const parsedOutput = parseToolOutput(item.tool_output)
  return buildToolMessage(
    {
      traceId: typeof metadata.trace_id === 'string' ? metadata.trace_id : undefined,
      requestId: typeof metadata.request_id === 'string' ? metadata.request_id : undefined,
      toolName: item.tool_name,
      displayName: typeof metadata.display_name === 'string' ? metadata.display_name : item.tool_name,
      phase: normalizeToolPhase(typeof metadata.status === 'string' ? metadata.status : undefined),
      inputPreview: buildToolPreview(item.tool_input),
      outputPreview: buildToolPreview(parsedOutput),
      inputPayload: item.tool_input || null,
      outputPayload: parsedOutput,
      error: typeof metadata.error === 'string' ? metadata.error : undefined,
      startedAt: typeof metadata.started_at === 'string' ? metadata.started_at : undefined,
      finishedAt: typeof metadata.finished_at === 'string' ? metadata.finished_at : undefined,
      isLive: false,
      persistedAt: item.created_at,
    },
    item.id,
    item.created_at
  )
}

function buildMessagesFromHistory(items: AgentSessionMessage[]): AgentMessageType[] {
  const messages: AgentMessageType[] = []

  for (const item of items) {
    const timestamp = new Date(item.created_at)
    const content = item.content?.trim() || ''
    const thinkingContent = item.thinking_content?.trim() || ''

    if (item.role === 'user' && content) {
      messages.push({
        id: item.id,
        content,
        timestamp,
        isAgent: false,
      })
      continue
    }

    if (item.role === 'tool') {
      const toolMessage = buildToolMessageFromHistory(item)
      if (toolMessage) {
        messages.push(toolMessage)
      }
      continue
    }

    if (thinkingContent) {
      messages.push({
        id: `${item.id}-thinking`,
        content: '',
        timestamp,
        isAgent: true,
        blockType: 'thinking_collapsed',
        thinkingContent,
        thinkingSummary: buildThinkingSummary(thinkingContent),
        thinkingLive: false,
      })
    }

    if (content) {
      messages.push({
        id: item.id,
        content,
        timestamp,
        isAgent: item.role !== 'user',
      })
    }
  }

  return messages.length ? messages : [createWelcomeMessage()]
}

function getSessionDisplayTitle(session: AgentSessionSummary): string {
  return session.title?.trim() || 'Nova conversa'
}

function formatSessionUpdatedAt(value?: string | null): string {
  const source = value ? new Date(value) : null
  if (!source || Number.isNaN(source.getTime())) {
    return 'Agora'
  }

  const now = new Date()
  const sameDay = source.toDateString() === now.toDateString()

  if (sameDay) {
    return source.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return source.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
  })
}

export function AgentChat() {
  const [messages, setMessages] = useState<AgentMessageType[]>([])
  const [liveThinkingBlock, setLiveThinkingBlock] = useState<AgentMessageType | null>(null)
  const [liveResponseBlock, setLiveResponseBlock] = useState<AgentMessageType | null>(null)
  const [isTyping, setIsTyping] = useState(false)
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [sessions, setSessions] = useState<AgentSessionSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isBootstrappingSession, setIsBootstrappingSession] = useState(true)
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)
  const [isSwitchingSession, setIsSwitchingSession] = useState(false)
  const [isSessionMenuOpen, setIsSessionMenuOpen] = useState(false)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const sessionsMenuRef = useRef<HTMLDivElement>(null)
  const sessionIdRef = useRef<string | undefined>(undefined)
  const sessionBootstrapPromiseRef = useRef<Promise<string> | null>(null)
  const requestSawThinkingRef = useRef(false)
  const requestSawResponseRef = useRef(false)
  const responseFinalizedRef = useRef(false)
  const activeThinkingRuntimeRef = useRef<ActiveThinkingRuntime | null>(null)
  const liveThinkingBlockRef = useRef<AgentMessageType | null>(null)
  const liveResponseBlockRef = useRef<AgentMessageType | null>(null)
  const pendingAssistantMessageRef = useRef<AgentMessageType | null>(null)
  const scrollAnimationFrameRef = useRef<number | null>(null)
  const autoScrollSnapshotRef = useRef<{
    messageCount: number
    lastMessageId: string | null
    liveThinkingId: string | null
    liveThinkingTokenCount: number
    liveResponseId: string | null
    liveResponseLength: number
  }>({
    messageCount: 0,
    lastMessageId: null,
    liveThinkingId: null,
    liveThinkingTokenCount: 0,
    liveResponseId: null,
    liveResponseLength: 0,
  })
  const { token } = useAuthStore()

  const cancelAutoScroll = useCallback(() => {
    if (scrollAnimationFrameRef.current !== null) {
      cancelAnimationFrame(scrollAnimationFrameRef.current)
      scrollAnimationFrameRef.current = null
    }
  }, [])

  const scrollToBottomInstant = useCallback(() => {
    const messagesContainer = messagesContainerRef.current
    if (!messagesContainer) {
      return
    }

    cancelAutoScroll()
    messagesContainer.scrollTop = Math.max(
      messagesContainer.scrollHeight - messagesContainer.clientHeight,
      0
    )
  }, [cancelAutoScroll])

  const followScrollToBottom = useCallback(() => {
    const messagesContainer = messagesContainerRef.current
    if (!messagesContainer || scrollAnimationFrameRef.current !== null) {
      return
    }

    const step = () => {
      const container = messagesContainerRef.current
      if (!container) {
        scrollAnimationFrameRef.current = null
        return
      }

      const targetTop = Math.max(container.scrollHeight - container.clientHeight, 0)
      const distance = targetTop - container.scrollTop

      if (distance <= AUTO_SCROLL_EPSILON_PX) {
        container.scrollTop = targetTop
        scrollAnimationFrameRef.current = null
        return
      }

      const delta = Math.min(
        Math.max(distance * AUTO_SCROLL_LERP, AUTO_SCROLL_MIN_STEP_PX),
        AUTO_SCROLL_MAX_STEP_PX
      )

      container.scrollTop = Math.min(container.scrollTop + delta, targetTop)
      scrollAnimationFrameRef.current = requestAnimationFrame(step)
    }

    step()
  }, [])

  useLayoutEffect(() => {
    const lastMessage = messages[messages.length - 1]
    const nextSnapshot = {
      messageCount: messages.length,
      lastMessageId: lastMessage?.id ?? null,
      liveThinkingId: liveThinkingBlock?.id ?? null,
      liveThinkingTokenCount: liveThinkingBlock?.thinkingTokens?.length ?? 0,
      liveResponseId: liveResponseBlock?.id ?? null,
      liveResponseLength: liveResponseBlock?.content.length ?? 0,
    }

    const previousSnapshot = autoScrollSnapshotRef.current
    const liveThinkingProgress =
      nextSnapshot.liveThinkingId !== null &&
      nextSnapshot.liveThinkingTokenCount !== previousSnapshot.liveThinkingTokenCount
    const liveResponseProgress =
      nextSnapshot.liveResponseId !== null &&
      nextSnapshot.liveResponseLength !== previousSnapshot.liveResponseLength
    const finalizedLiveBlock =
      (previousSnapshot.liveThinkingId !== null && nextSnapshot.liveThinkingId === null) ||
      (previousSnapshot.liveResponseId !== null && nextSnapshot.liveResponseId === null)
    const isBulkHistorySync =
      Math.abs(nextSnapshot.messageCount - previousSnapshot.messageCount) >=
      BULK_SCROLL_SYNC_THRESHOLD
    const shouldScroll =
      nextSnapshot.messageCount !== previousSnapshot.messageCount ||
      nextSnapshot.lastMessageId !== previousSnapshot.lastMessageId ||
      nextSnapshot.liveThinkingId !== previousSnapshot.liveThinkingId ||
      (nextSnapshot.liveThinkingId !== null &&
        nextSnapshot.liveThinkingTokenCount !== previousSnapshot.liveThinkingTokenCount) ||
      nextSnapshot.liveResponseId !== previousSnapshot.liveResponseId ||
      (nextSnapshot.liveResponseId !== null &&
        nextSnapshot.liveResponseLength !== previousSnapshot.liveResponseLength)

    autoScrollSnapshotRef.current = nextSnapshot

    if (shouldScroll) {
      if (isBulkHistorySync && !liveThinkingProgress && !liveResponseProgress && !finalizedLiveBlock) {
        scrollToBottomInstant()
      } else {
        followScrollToBottom()
      }
    }
  }, [followScrollToBottom, liveResponseBlock, liveThinkingBlock, messages, scrollToBottomInstant])

  const applySessionId = useCallback((nextSessionId: string) => {
    const previousSessionId = sessionIdRef.current
    if (previousSessionId && previousSessionId !== nextSessionId) {
      socketService.leaveAgentChat(previousSessionId)
    }

    sessionIdRef.current = nextSessionId
    setSessionId(nextSessionId)
    void socketService.joinAgentChat(nextSessionId)

    if (typeof window !== 'undefined') {
      window.localStorage.setItem(AGENT_SESSION_STORAGE_KEY, nextSessionId)
    }
  }, [])

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true)

    try {
      const response = await agentService.getSessions()
      setSessions(response.items)
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Não foi possível carregar as sessões recentes'
      setError((current) => current || message)
    } finally {
      setIsLoadingSessions(false)
    }
  }, [])

  const loadSessionHistory = useCallback(async (nextSessionId: string) => {
    const history = await agentService.getSessionMessages(nextSessionId)
    setMessages(buildMessagesFromHistory(history.items))
  }, [])

  const bootstrapSession = useCallback(async (): Promise<string> => {
    setIsBootstrappingSession(true)

    try {
      const storedSessionId =
        typeof window !== 'undefined'
          ? window.localStorage.getItem(AGENT_SESSION_STORAGE_KEY)
          : null

      if (storedSessionId) {
        try {
          applySessionId(storedSessionId)
          await loadSessionHistory(storedSessionId)
          await loadSessions()
          return storedSessionId
        } catch {
          if (typeof window !== 'undefined') {
            window.localStorage.removeItem(AGENT_SESSION_STORAGE_KEY)
          }
        }
      }

      const { session_id: createdSessionId } = await agentService.createSession()
      applySessionId(createdSessionId)
      setMessages([createWelcomeMessage()])
      await loadSessions()
      return createdSessionId
    } finally {
      setIsBootstrappingSession(false)
    }
  }, [applySessionId, loadSessionHistory, loadSessions])

  const ensureSessionId = useCallback(async (): Promise<string> => {
    if (sessionIdRef.current) {
      return sessionIdRef.current
    }

    if (!sessionBootstrapPromiseRef.current) {
      sessionBootstrapPromiseRef.current = bootstrapSession().finally(() => {
        sessionBootstrapPromiseRef.current = null
      })
    }

    return sessionBootstrapPromiseRef.current
  }, [bootstrapSession])

  const upsertToolMessage = useCallback((toolEvent: AgentToolEvent) => {
    const toolId =
      toolEvent.traceId ||
      `${toolEvent.requestId || sessionIdRef.current || 'tool'}:${toolEvent.toolName}:${toolEvent.phase}`

    setMessages((prev) => {
      const nextMessage = buildToolMessage(toolEvent, `tool-${toolId}`)
      const existingIndex = prev.findIndex((message) => message.id === nextMessage.id)

      if (existingIndex === -1) {
        return [...prev, nextMessage]
      }

      const updated = [...prev]
      updated[existingIndex] = {
        ...updated[existingIndex],
        ...nextMessage,
        timestamp: updated[existingIndex].timestamp,
      }
      return updated
    })
  }, [])

  const appendThinkingTokens = useCallback((thinkingId: string, tokens: string[]) => {
    if (!tokens.length) {
      return
    }

    setLiveThinkingBlock((prev) => {
      if (!prev || prev.id !== thinkingId) {
        return prev
      }

      const nextBlock = {
        ...prev,
        blockType: 'thinking_streaming' as const,
        thinkingTokens: [...(prev.thinkingTokens || []), ...tokens],
        thinkingLive: true,
      }

      liveThinkingBlockRef.current = nextBlock
      return nextBlock
    })
  }, [])

  const collapseThinkingMessage = useCallback((thinkingId: string, fallbackContent?: string) => {
    const currentLiveBlock = liveThinkingBlockRef.current
    if (!currentLiveBlock || currentLiveBlock.id !== thinkingId) {
      return
    }

    const fullThinking = (currentLiveBlock.thinkingTokens || []).join('').trim()
    const collapsedMessage: AgentMessageType = {
      id: thinkingId,
      content: '',
      timestamp: currentLiveBlock.timestamp,
      isAgent: true,
      blockType: 'thinking_collapsed',
      thinkingContent: fullThinking || fallbackContent || 'Pensamento concluído',
      thinkingSummary: buildThinkingSummary(fullThinking || fallbackContent || 'Pensamento concluído'),
      thinkingLive: false,
    }

    liveThinkingBlockRef.current = null
    setLiveThinkingBlock(null)
    setMessages((prev) => [...prev, collapsedMessage])
  }, [])

  const appendPendingAssistantMessage = useCallback(() => {
    const pendingAssistantMessage = pendingAssistantMessageRef.current
    if (!pendingAssistantMessage) {
      return
    }

    if (requestSawResponseRef.current || liveResponseBlockRef.current || responseFinalizedRef.current) {
      pendingAssistantMessageRef.current = null
      return
    }

    pendingAssistantMessageRef.current = null
    responseFinalizedRef.current = true
    setMessages((prev) => [...prev, pendingAssistantMessage])
  }, [])

  const startLiveResponse = useCallback((responseId?: string) => {
    setLiveResponseBlock((prev) => {
      if (prev) {
        return prev
      }

      const nextBlock: AgentMessageType = {
        id: responseId || `response-${sessionIdRef.current || Date.now()}`,
        content: '',
        timestamp: new Date(),
        isAgent: true,
        streaming: true,
      }

      liveResponseBlockRef.current = nextBlock
      return nextBlock
    })
  }, [])

  const appendResponseToken = useCallback((token: string) => {
    if (!token) {
      return
    }

    setLiveResponseBlock((prev) => {
      const baseBlock =
        prev ||
        liveResponseBlockRef.current || {
          id: `response-${sessionIdRef.current || Date.now()}`,
          content: '',
          timestamp: new Date(),
          isAgent: true,
          streaming: true,
        }

      const nextBlock: AgentMessageType = {
        ...baseBlock,
        content: `${baseBlock.content}${token}`,
        streaming: true,
      }

      liveResponseBlockRef.current = nextBlock
      return nextBlock
    })
  }, [])

  const finalizeLiveResponse = useCallback((fallbackContent?: string, responseId?: string) => {
    const currentBlock = liveResponseBlockRef.current
    const finalContent = (fallbackContent ?? currentBlock?.content ?? '').trim()

    if (!currentBlock && !finalContent) {
      return
    }

    const finalizedMessage: AgentMessageType = {
      id: responseId || currentBlock?.id || `response-${Date.now()}`,
      content: finalContent,
      timestamp: currentBlock?.timestamp || new Date(),
      isAgent: true,
      streaming: false,
    }

    liveResponseBlockRef.current = null
    responseFinalizedRef.current = true
    setLiveResponseBlock(null)
    setMessages((prev) => [...prev, finalizedMessage])
  }, [])

  const reconcileLiveResponseWithFinal = useCallback((messageId: string, finalContent: string) => {
    if (responseFinalizedRef.current) {
      return true
    }

    const currentBlock = liveResponseBlockRef.current
    if (!currentBlock) {
      return false
    }

    const reconciledMessage: AgentMessageType = {
      ...currentBlock,
      id: messageId,
      content: finalContent || currentBlock.content,
      streaming: false,
    }

    liveResponseBlockRef.current = null
    responseFinalizedRef.current = true
    setLiveResponseBlock(null)
    setMessages((prev) => [...prev, reconciledMessage])
    return true
  }, [])

  const clearThinkingRuntimeTimers = useCallback((runtime: ActiveThinkingRuntime | null) => {
    if (!runtime) {
      return
    }

    if (runtime.indicatorTimer) {
      clearTimeout(runtime.indicatorTimer)
      runtime.indicatorTimer = null
    }

    if (runtime.drainTimer) {
      clearTimeout(runtime.drainTimer)
      runtime.drainTimer = null
    }

    if (runtime.finalizeTimer) {
      clearTimeout(runtime.finalizeTimer)
      runtime.finalizeTimer = null
    }

    if (runtime.forceFinalizeTimer) {
      clearTimeout(runtime.forceFinalizeTimer)
      runtime.forceFinalizeTimer = null
    }
  }, [])

  const clearTransientChatState = useCallback(() => {
    cancelAutoScroll()
    clearThinkingRuntimeTimers(activeThinkingRuntimeRef.current)
    activeThinkingRuntimeRef.current = null
    pendingAssistantMessageRef.current = null
    liveThinkingBlockRef.current = null
    liveResponseBlockRef.current = null
    requestSawThinkingRef.current = false
    requestSawResponseRef.current = false
    responseFinalizedRef.current = false
    setIsTyping(false)
    setLiveThinkingBlock(null)
    setLiveResponseBlock(null)
  }, [cancelAutoScroll, clearThinkingRuntimeTimers])

  const finalizeThinkingRuntime = useCallback(
    (fallbackContent?: string) => {
      const runtime = activeThinkingRuntimeRef.current
      if (!runtime) {
        appendPendingAssistantMessage()
        return
      }

      clearThinkingRuntimeTimers(runtime)
      collapseThinkingMessage(
        runtime.id,
        fallbackContent || runtime.fallbackContent || runtime.endSummary || 'Pensamento concluído'
      )
      activeThinkingRuntimeRef.current = null
      appendPendingAssistantMessage()
    },
    [appendPendingAssistantMessage, clearThinkingRuntimeTimers, collapseThinkingMessage]
  )

  const flushThinkingBeforeToolEvent = useCallback(() => {
    const runtime = activeThinkingRuntimeRef.current
    const liveBlock = liveThinkingBlockRef.current

    if (!runtime) {
      return
    }

    if (liveBlock) {
      const mergedTokens = [...(liveBlock.thinkingTokens || []), ...runtime.queuedTokens]
      liveThinkingBlockRef.current = {
        ...liveBlock,
        blockType: mergedTokens.length ? 'thinking_streaming' : liveBlock.blockType,
        thinkingTokens: mergedTokens,
        thinkingLive: false,
      }
      runtime.queuedTokens = []
      runtime.hasEnded = true
      finalizeThinkingRuntime(
        mergedTokens.join('').trim() || runtime.endSummary || runtime.fallbackContent
      )
      return
    }

    finalizeThinkingRuntime(runtime.endSummary || runtime.fallbackContent)
  }, [finalizeThinkingRuntime])

  const maybeFinalizeThinkingRuntime = useCallback(() => {
    const runtime = activeThinkingRuntimeRef.current
    if (!runtime || !runtime.hasEnded) {
      return
    }

    if (runtime.queuedTokens.length > 0) {
      return
    }

    if (runtime.stage === 'streaming' && runtime.streamingStartedAt) {
      const elapsedStreaming = Date.now() - runtime.streamingStartedAt
      const remainingStreaming = MIN_THINKING_STREAMING_MS - elapsedStreaming

      if (remainingStreaming > 0) {
        if (!runtime.finalizeTimer) {
          runtime.finalizeTimer = setTimeout(() => {
            const currentRuntime = activeThinkingRuntimeRef.current
            if (currentRuntime) {
              currentRuntime.finalizeTimer = null
            }
            maybeFinalizeThinkingRuntime()
          }, remainingStreaming)
        }
        return
      }
    }

    finalizeThinkingRuntime()
  }, [finalizeThinkingRuntime])

  const drainThinkingQueue = useCallback(() => {
    const runtime = activeThinkingRuntimeRef.current
    if (!runtime) {
      return
    }

    const elapsedIndicator = Date.now() - runtime.startedAt
    const remainingIndicator = MIN_THINKING_INDICATOR_MS - elapsedIndicator

    if (runtime.stage === 'indicator' && remainingIndicator > 0) {
      if (!runtime.indicatorTimer) {
        runtime.indicatorTimer = setTimeout(() => {
          const currentRuntime = activeThinkingRuntimeRef.current
          if (currentRuntime) {
            currentRuntime.indicatorTimer = null
          }
          drainThinkingQueue()
        }, remainingIndicator)
      }
      return
    }

    if (runtime.stage === 'indicator') {
      runtime.stage = 'streaming'
      runtime.streamingStartedAt = Date.now()
    }

    if (!runtime.queuedTokens.length) {
      maybeFinalizeThinkingRuntime()
      return
    }

    const nextTokens = runtime.queuedTokens.splice(0, THINKING_DRAIN_BATCH_SIZE)
    appendThinkingTokens(runtime.id, nextTokens)

    if (runtime.queuedTokens.length > 0) {
      runtime.drainTimer = setTimeout(() => {
        const currentRuntime = activeThinkingRuntimeRef.current
        if (currentRuntime) {
          currentRuntime.drainTimer = null
        }
        drainThinkingQueue()
      }, THINKING_DRAIN_INTERVAL_MS)
      return
    }

    maybeFinalizeThinkingRuntime()
  }, [appendThinkingTokens, maybeFinalizeThinkingRuntime])

  const replayThinkingFromFinalContent = useCallback(
    (finalThinking: string) => {
      const runtime = activeThinkingRuntimeRef.current
      if (!runtime) {
        return false
      }

      const normalizedFinalThinking = finalThinking.trim()
      if (!normalizedFinalThinking) {
        return false
      }

      const visibleThinking = (liveThinkingBlockRef.current?.thinkingTokens || []).join('')
      const queuedThinking = runtime.queuedTokens.join('')
      const currentThinking = `${visibleThinking}${queuedThinking}`

      let missingContent = ''

      if (!currentThinking) {
        missingContent = normalizedFinalThinking
      } else if (normalizedFinalThinking.startsWith(currentThinking)) {
        missingContent = normalizedFinalThinking.slice(currentThinking.length)
      } else if (!runtime.sawThinkingTokens) {
        runtime.queuedTokens = []
        missingContent = normalizedFinalThinking
      }

      if (!missingContent) {
        return false
      }

      runtime.queuedTokens.push(...Array.from(missingContent))
      runtime.sawThinkingTokens = true
      runtime.hasEnded = true
      runtime.endSummary = normalizedFinalThinking

      if (runtime.forceFinalizeTimer) {
        clearTimeout(runtime.forceFinalizeTimer)
        runtime.forceFinalizeTimer = null
      }

      const elapsedIndicator = Date.now() - runtime.startedAt
      const remainingIndicator = MIN_THINKING_INDICATOR_MS - elapsedIndicator

      if (runtime.stage === 'indicator' && remainingIndicator > 0) {
        if (!runtime.indicatorTimer) {
          runtime.indicatorTimer = setTimeout(() => {
            const currentRuntime = activeThinkingRuntimeRef.current
            if (currentRuntime) {
              currentRuntime.indicatorTimer = null
            }
            drainThinkingQueue()
          }, remainingIndicator)
        }
        return true
      }

      if (!runtime.drainTimer) {
        runtime.drainTimer = setTimeout(() => {
          const currentRuntime = activeThinkingRuntimeRef.current
          if (currentRuntime) {
            currentRuntime.drainTimer = null
          }
          drainThinkingQueue()
        }, THINKING_DRAIN_INTERVAL_MS)
      }

      return true
    },
    [drainThinkingQueue]
  )

  const handleThinkingEvent = useCallback((event: string, data?: Record<string, unknown>) => {
    const currentSessionId = sessionIdRef.current
    const eventSessionId =
      typeof data?.conversationId === 'string' ? data.conversationId : undefined

    if (currentSessionId && eventSessionId && eventSessionId !== currentSessionId) {
      return
    }

    switch (event) {
      case 'thinking_start': {
        requestSawThinkingRef.current = true
        const existingRuntime = activeThinkingRuntimeRef.current
        const existingLiveBlock = liveThinkingBlockRef.current

        if (
          existingRuntime &&
          existingLiveBlock &&
          existingLiveBlock.blockType === 'thinking_indicator' &&
          !existingRuntime.hasEnded
        ) {
          existingRuntime.startedAt = Math.min(existingRuntime.startedAt, Date.now())
          return
        }

        const thinkingId = `thinking-${eventSessionId || currentSessionId || Date.now()}-${Date.now()}`
        if (existingRuntime) {
          finalizeThinkingRuntime()
        }

        activeThinkingRuntimeRef.current = {
          id: thinkingId,
          startedAt: Date.now(),
          stage: 'indicator',
          queuedTokens: [],
          sawThinkingTokens: false,
          hasEnded: false,
          indicatorTimer: null,
          drainTimer: null,
          finalizeTimer: null,
          forceFinalizeTimer: null,
        }

        const thinkingBlock: AgentMessageType = {
          id: thinkingId,
          content: '',
          timestamp: new Date(),
          isAgent: true,
          blockType: 'thinking_indicator',
          thinkingTokens: [],
          thinkingLive: true,
        }

        liveThinkingBlockRef.current = thinkingBlock
        setLiveThinkingBlock(thinkingBlock)
        break
      }

      case 'thinking_token': {
        const tokenValue = typeof data?.token === 'string' ? data.token : ''
        const runtime = activeThinkingRuntimeRef.current
        if (!tokenValue || !runtime) {
          return
        }

        runtime.queuedTokens.push(...Array.from(tokenValue))
        runtime.sawThinkingTokens = true

        const elapsedIndicator = Date.now() - runtime.startedAt
        const remainingIndicator = MIN_THINKING_INDICATOR_MS - elapsedIndicator

        if (runtime.stage === 'indicator' && remainingIndicator > 0) {
          if (!runtime.indicatorTimer) {
            runtime.indicatorTimer = setTimeout(() => {
              const currentRuntime = activeThinkingRuntimeRef.current
              if (currentRuntime) {
                currentRuntime.indicatorTimer = null
              }
              drainThinkingQueue()
            }, remainingIndicator)
          }
          return
        }

        if (!runtime.drainTimer) {
          runtime.drainTimer = setTimeout(() => {
            const currentRuntime = activeThinkingRuntimeRef.current
            if (currentRuntime) {
              currentRuntime.drainTimer = null
            }
            drainThinkingQueue()
          }, THINKING_DRAIN_INTERVAL_MS)
        }
        break
      }

      case 'thinking_end': {
        const runtime = activeThinkingRuntimeRef.current
        if (!runtime) {
          return
        }

        runtime.hasEnded = true
        runtime.endSummary =
          typeof data?.summary === 'string' && data.summary.trim()
            ? data.summary.trim()
            : 'Pensamento concluído'

        if (!runtime.queuedTokens.length && runtime.stage === 'indicator') {
          const elapsedIndicator = Date.now() - runtime.startedAt
          const remainingIndicator = MIN_THINKING_INDICATOR_MS - elapsedIndicator

          if (remainingIndicator > 0) {
            if (!runtime.indicatorTimer) {
              runtime.indicatorTimer = setTimeout(() => {
                const currentRuntime = activeThinkingRuntimeRef.current
                if (currentRuntime) {
                  currentRuntime.indicatorTimer = null
                }
                finalizeThinkingRuntime(runtime.endSummary)
              }, remainingIndicator)
            }
            return
          }

          finalizeThinkingRuntime(runtime.endSummary)
          return
        }

        if (!runtime.drainTimer) {
          runtime.drainTimer = setTimeout(() => {
            const currentRuntime = activeThinkingRuntimeRef.current
            if (currentRuntime) {
              currentRuntime.drainTimer = null
            }
            drainThinkingQueue()
          }, THINKING_DRAIN_INTERVAL_MS)
        }
        break
      }

      case 'response_start': {
        if (responseFinalizedRef.current && !liveResponseBlockRef.current) {
          return
        }
        requestSawResponseRef.current = true
        pendingAssistantMessageRef.current = null
        startLiveResponse()
        break
      }

      case 'response_token': {
        if (responseFinalizedRef.current && !liveResponseBlockRef.current) {
          return
        }
        const tokenValue = typeof data?.token === 'string' ? data.token : ''
        if (!tokenValue) {
          return
        }

        requestSawResponseRef.current = true
        if (!liveResponseBlockRef.current) {
          startLiveResponse()
        }
        appendResponseToken(tokenValue)
        break
      }

      case 'response_end': {
        if (responseFinalizedRef.current && !liveResponseBlockRef.current) {
          return
        }
        requestSawResponseRef.current = true
        const finalContent = typeof data?.content === 'string' ? data.content : undefined
        finalizeLiveResponse(finalContent)
        break
      }

      case 'tool_waiting_input':
      case 'tool_started':
      case 'tool_completed':
      case 'tool_failed': {
        if (activeThinkingRuntimeRef.current) {
          flushThinkingBeforeToolEvent()
        }

        const toolName = typeof data?.toolName === 'string' ? data.toolName : 'tool'
        const phaseByEvent: Record<string, AgentToolEvent['phase']> = {
          tool_waiting_input: 'waiting_input',
          tool_started: 'started',
          tool_completed: 'completed',
          tool_failed: 'failed',
        }

        upsertToolMessage({
          traceId: typeof data?.traceId === 'string' ? data.traceId : undefined,
          requestId: typeof data?.requestId === 'string' ? data.requestId : undefined,
          source: typeof data?.source === 'string' ? data.source : undefined,
          toolName,
          displayName: typeof data?.displayName === 'string' ? data.displayName : toolName,
          phase: phaseByEvent[event] || 'completed',
          inputPreview:
            typeof data?.inputPreview === 'string'
              ? data.inputPreview
              : buildToolPreview(data?.inputPayload),
          outputPreview:
            typeof data?.outputPreview === 'string'
              ? data.outputPreview
              : buildToolPreview(data?.outputPayload),
          inputPayload:
            data?.inputPayload && typeof data.inputPayload === 'object'
              ? (data.inputPayload as Record<string, unknown>)
              : null,
          outputPayload: data?.outputPayload,
          error: typeof data?.error === 'string' ? data.error : undefined,
          startedAt: typeof data?.startedAt === 'string' ? data.startedAt : undefined,
          finishedAt: typeof data?.finishedAt === 'string' ? data.finishedAt : undefined,
          isLive: true,
          persistedAt: new Date().toISOString(),
        })
        break
      }
    }
  }, [appendResponseToken, drainThinkingQueue, finalizeLiveResponse, finalizeThinkingRuntime, flushThinkingBeforeToolEvent, startLiveResponse, upsertToolMessage])

  const handleCreateNewSession = useCallback(async () => {
    setIsSwitchingSession(true)
    setError(null)
    setIsSessionMenuOpen(false)

    try {
      clearTransientChatState()
      const { session_id: createdSessionId } = await agentService.createSession()
      applySessionId(createdSessionId)
      setMessages([createWelcomeMessage()])
      await loadSessions()
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Não foi possível criar uma nova sessão'
      setError(message)
    } finally {
      setIsSwitchingSession(false)
    }
  }, [applySessionId, clearTransientChatState, loadSessions])

  const handleSelectSession = useCallback(
    async (nextSessionId: string) => {
      if (!nextSessionId || nextSessionId === sessionIdRef.current) {
        setIsSessionMenuOpen(false)
        return
      }

      setIsSwitchingSession(true)
      setError(null)
      setIsSessionMenuOpen(false)

      try {
        clearTransientChatState()
        applySessionId(nextSessionId)
        await loadSessionHistory(nextSessionId)
        await loadSessions()
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Não foi possível abrir a sessão selecionada'
        setError(message)
      } finally {
        setIsSwitchingSession(false)
      }
    },
    [applySessionId, clearTransientChatState, loadSessionHistory, loadSessions]
  )

  useEffect(() => {
    void ensureSessionId().catch((err) => {
      const message =
        err instanceof Error ? err.message : 'Não foi possível preparar o chat do agente'
      setError(message)
      setMessages([createWelcomeMessage()])
      setIsBootstrappingSession(false)
    })
  }, [ensureSessionId])

  useEffect(() => {
    if (!token) {
      return
    }

    socketService.setAgentThinkingCallback(handleThinkingEvent)

    const currentSessionId = sessionIdRef.current
    if (currentSessionId) {
      void socketService.ensureAgentChatReady(currentSessionId, token)
    } else {
      void socketService.connectForAgentChat(token)
    }

    return () => {
      socketService.setAgentThinkingCallback(null)

      const activeSessionId = sessionIdRef.current
      if (activeSessionId) {
        socketService.leaveAgentChat(activeSessionId)
      }
    }
  }, [handleThinkingEvent, token, sessionId])

  useEffect(() => {
    return () => {
      cancelAutoScroll()
      clearTransientChatState()
    }
  }, [cancelAutoScroll, clearTransientChatState])

  useEffect(() => {
    if (!isSessionMenuOpen) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (
        sessionsMenuRef.current &&
        !sessionsMenuRef.current.contains(event.target as Node)
      ) {
        setIsSessionMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handlePointerDown)
    return () => document.removeEventListener('mousedown', handlePointerDown)
  }, [isSessionMenuOpen])

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) {
        return
      }

      const userMessage: AgentMessageType = {
        id: `user-${Date.now()}`,
        content,
        timestamp: new Date(),
        isAgent: false,
      }

      setMessages((prev) => [...prev, userMessage])
      setIsTyping(true)
      setError(null)
      requestSawThinkingRef.current = false
      requestSawResponseRef.current = false
      responseFinalizedRef.current = false
      pendingAssistantMessageRef.current = null
      liveResponseBlockRef.current = null
      setLiveResponseBlock(null)

      const optimisticThinkingId = `thinking-local-${Date.now()}`
      const optimisticThinkingBlock: AgentMessageType = {
        id: optimisticThinkingId,
        content: '',
        timestamp: new Date(),
        isAgent: true,
        blockType: 'thinking_indicator',
        thinkingTokens: [],
        thinkingLive: true,
      }

      clearThinkingRuntimeTimers(activeThinkingRuntimeRef.current)
      activeThinkingRuntimeRef.current = {
        id: optimisticThinkingId,
        startedAt: Date.now(),
        stage: 'indicator',
        queuedTokens: [],
        sawThinkingTokens: false,
        hasEnded: false,
        indicatorTimer: null,
        drainTimer: null,
        finalizeTimer: null,
        forceFinalizeTimer: null,
      }
      liveThinkingBlockRef.current = optimisticThinkingBlock
      setLiveThinkingBlock(optimisticThinkingBlock)

      try {
        const resolvedSessionId = await ensureSessionId()
        await socketService.ensureAgentChatReady(resolvedSessionId, token || undefined)
        const response = await agentService.sendMessage(content, resolvedSessionId)

        if (response.session_id && response.session_id !== sessionIdRef.current) {
          applySessionId(response.session_id)
        }

        void loadSessions()

        const responseThinking = response.thinking?.trim()
        const requestSawThinking = requestSawThinkingRef.current
        const assistantMessage: AgentMessageType = {
          id: response.message_id,
          content: response.response,
          timestamp: new Date(),
          isAgent: true,
        }
        const activeRuntime = activeThinkingRuntimeRef.current
        const sawThinkingStream = requestSawThinking || activeRuntime?.sawThinkingTokens
        const sawResponseStream = requestSawResponseRef.current

        if (sawResponseStream) {
          pendingAssistantMessageRef.current = null
          reconcileLiveResponseWithFinal(response.message_id, response.response)
        }

        if (activeRuntime || requestSawThinking) {
          if (!sawResponseStream) {
            pendingAssistantMessageRef.current = assistantMessage
          }

          if (activeRuntime) {
            if (responseThinking) {
              activeRuntime.fallbackContent = responseThinking
              if (!activeRuntime.endSummary) {
                activeRuntime.endSummary = responseThinking
              }

              if (sawThinkingStream && replayThinkingFromFinalContent(responseThinking)) {
                return
              }

              if (!sawThinkingStream) {
                finalizeThinkingRuntime(responseThinking)
                return
              }
            }

            if (activeRuntime.forceFinalizeTimer) {
              clearTimeout(activeRuntime.forceFinalizeTimer)
            }

            activeRuntime.forceFinalizeTimer = setTimeout(() => {
              const currentRuntime = activeThinkingRuntimeRef.current
              if (!currentRuntime) {
                appendPendingAssistantMessage()
                return
              }

              currentRuntime.forceFinalizeTimer = null
              currentRuntime.hasEnded = true

              if (currentRuntime.queuedTokens.length > 0 || currentRuntime.stage === 'streaming') {
                drainThinkingQueue()
                return
              }

              finalizeThinkingRuntime(responseThinking)
            }, THINKING_END_GRACE_MS)
          } else {
            appendPendingAssistantMessage()
          }
        } else {
          if (sawResponseStream) {
            return
          }

          responseFinalizedRef.current = true
          setMessages((prev) => {
            if (!responseThinking) {
              return [...prev, assistantMessage]
            }

            return [
              ...prev,
              {
                id: `${response.message_id}-thinking`,
                content: '',
                timestamp: new Date(),
                isAgent: true,
                blockType: 'thinking_collapsed',
                thinkingContent: responseThinking,
                thinkingSummary: buildThinkingSummary(responseThinking),
                thinkingLive: false,
              },
              assistantMessage,
            ]
          })
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Erro ao processar mensagem'

        pendingAssistantMessageRef.current = null
        finalizeThinkingRuntime('Erro ao gerar pensamento')
        if (liveResponseBlockRef.current) {
          finalizeLiveResponse(undefined)
        }
        setError(errorMessage)

        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}`,
            content: `Desculpe, ocorreu um erro: ${errorMessage}. Por favor, tente novamente.`,
            timestamp: new Date(),
            isAgent: true,
          },
        ])
      } finally {
        requestSawThinkingRef.current = false
        setIsTyping(false)
      }
    },
    [
      appendPendingAssistantMessage,
      applySessionId,
      clearThinkingRuntimeTimers,
      drainThinkingQueue,
      ensureSessionId,
      finalizeLiveResponse,
      finalizeThinkingRuntime,
      loadSessions,
      replayThinkingFromFinalContent,
      reconcileLiveResponseWithFinal,
      token,
    ]
  )

  const handleExpandThinking = useCallback((thinkingId: string) => {
    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== thinkingId || message.blockType !== 'thinking_collapsed') {
          return message
        }

        return {
          ...message,
          blockType: 'thinking_streaming' as const,
          thinkingTokens: message.thinkingContent ? message.thinkingContent.split('') : [],
          thinkingContent: undefined,
          thinkingLive: false,
        }
      })
    )
  }, [])

  const handleCollapseThinking = useCallback((thinkingId: string) => {
    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== thinkingId || message.blockType !== 'thinking_streaming') {
          return message
        }

        return {
          ...message,
          blockType: 'thinking_collapsed' as const,
          thinkingContent: (message.thinkingTokens || []).join('').trim(),
          thinkingSummary: buildThinkingSummary((message.thinkingTokens || []).join('').trim()),
          thinkingTokens: undefined,
          thinkingLive: false,
        }
      })
    )
  }, [])

  const currentSessionSummary =
    sessions.find((currentSession) => currentSession.id === sessionId) || null
  const isComposerDisabled = isTyping || isBootstrappingSession || isSwitchingSession

  return (
    <div className="flex h-full min-h-0 flex-col bg-card">
      <div className="flex items-center justify-between border-b border-border-color px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary">
            <svg
              className="h-5 w-5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2 2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold text-text-light">Assistente Neuralilux</h3>
            <p className="text-sm text-text-muted">
              {isSwitchingSession
                ? 'Abrindo outra sessão'
                : currentSessionSummary
                  ? `Sessão: ${getSessionDisplayTitle(currentSessionSummary)}`
                  : sessionId
                    ? 'Online e acompanhando esta sessão'
                    : 'Preparando sessão'}
            </p>
          </div>
        </div>
        <div ref={sessionsMenuRef} className="relative flex items-center gap-2">
          <button
            className={`rounded-lg p-2 transition-colors hover:bg-hover ${isSessionMenuOpen ? 'bg-hover' : ''
              }`}
            type="button"
            aria-label="Sessões recentes"
            onClick={() => setIsSessionMenuOpen((current) => !current)}
          >
            <Clock3 className="h-5 w-5 text-text-gray" />
          </button>
          {isSessionMenuOpen && (
            <div className="absolute right-0 top-12 z-20 w-[360px] rounded-2xl border border-border-color bg-card p-3 shadow-2xl">
              <div className="mb-3 flex items-center justify-between gap-3 px-2">
                <div>
                  <p className="text-sm font-semibold text-text-light">Sessões recentes</p>
                  <p className="text-xs text-text-muted">
                    Cada sessão mantém o próprio histórico salvo no banco.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleCreateNewSession()}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-primary/90"
                >
                  <Plus className="h-4 w-4" />
                  Nova sessão
                </button>
              </div>

              <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                {isLoadingSessions ? (
                  <div className="rounded-xl border border-border-color bg-dark px-4 py-6 text-center text-sm text-text-muted">
                    Carregando sessões...
                  </div>
                ) : sessions.length ? (
                  sessions.map((session) => {
                    const isActive = session.id === sessionId

                    return (
                      <button
                        key={session.id}
                        type="button"
                        onClick={() => void handleSelectSession(session.id)}
                        className={`flex w-full flex-col rounded-xl border px-4 py-3 text-left transition-colors ${isActive
                            ? 'border-primary bg-primary/10'
                            : 'border-border-color bg-dark hover:border-primary/40 hover:bg-hover'
                          }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="line-clamp-1 text-sm font-semibold text-text-light">
                            {getSessionDisplayTitle(session)}
                          </p>
                          <span className="text-[11px] text-text-muted">
                            {formatSessionUpdatedAt(session.updated_at || session.created_at)}
                          </span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-xs leading-5 text-text-gray">
                          {session.last_message_preview?.trim() || 'Sem mensagens nesta sessão ainda.'}
                        </p>
                      </button>
                    )
                  })
                ) : (
                  <div className="rounded-xl border border-border-color bg-dark px-4 py-6 text-center text-sm text-text-muted">
                    Nenhuma sessão recente encontrada.
                  </div>
                )}
              </div>
            </div>
          )}
          <button className="rounded-lg p-2 hover:bg-hover" type="button" aria-label="Buscar">
            <Search className="h-5 w-5 text-text-gray" />
          </button>
          <button className="rounded-lg p-2 hover:bg-hover" type="button" aria-label="Mais opções">
            <MoreVertical className="h-5 w-5 text-text-gray" />
          </button>
        </div>
      </div>

      <div
        ref={messagesContainerRef}
        className="min-h-0 flex-1 overflow-y-auto p-6"
        style={{ overflowAnchor: 'none' }}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-center">
            <span className="rounded-full bg-hover px-3 py-1 text-xs text-text-muted">
              Hoje
            </span>
          </div>

          {messages.map((message) => (
            <AgentMessage
              key={message.id}
              message={message}
              onExpandThinking={handleExpandThinking}
              onCollapseThinking={handleCollapseThinking}
            />
          ))}

          {liveThinkingBlock && (
            <AgentMessage
              key={liveThinkingBlock.id}
              message={liveThinkingBlock}
              onExpandThinking={handleExpandThinking}
              onCollapseThinking={handleCollapseThinking}
            />
          )}

          {liveResponseBlock && (
            <AgentMessage
              key={liveResponseBlock.id}
              message={liveResponseBlock}
              onExpandThinking={handleExpandThinking}
              onCollapseThinking={handleCollapseThinking}
            />
          )}

          {isTyping &&
            !liveThinkingBlock && !liveResponseBlock && (
              <div className="flex items-start gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary">
                  <svg
                    className="h-4 w-4 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2 2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <div className="rounded-2xl bg-hover px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-text-muted" />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-text-muted"
                      style={{ animationDelay: '0.1s' }}
                    />
                    <span
                      className="h-2 w-2 animate-bounce rounded-full bg-text-muted"
                      style={{ animationDelay: '0.2s' }}
                    />
                  </div>
                </div>
              </div>
            )}

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}
        </div>
      </div>

      <AgentInputBar
        onSendMessage={handleSendMessage}
        disabled={isComposerDisabled}
      />
    </div>
  )
}
