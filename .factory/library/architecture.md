# Architecture

How the Neuralilux system works — components, relationships, data flows.

## System Components

| Component | Technology | Port | Role |
|-----------|-----------|------|------|
| Frontend | Next.js 14 (App Router) | 3000 | Dashboard UI for managing WhatsApp agents |
| Backend API | FastAPI + python-socketio | 8000 | REST API + socket.io server |
| LM Studio | Local LLM server (OpenAI-compatible) | 1234 | Hosts local AI models (Qwen3.5, nemotron) |
| Redis | Redis 7 (Docker) | 6380 | Pub/sub for realtime events + caching |
| PostgreSQL | Postgres 15 (Docker) | 5434 | Persistent storage (messages, sessions, agents) |
| Evolution API | WhatsApp API wrapper (Docker) | 8081 | Send/receive WhatsApp messages |
| RabbitMQ | Message broker (Docker) | 5672 | Async message queuing |

## Realtime Event Flow (ThinkingBubble)

The ThinkingBubble displays the AI agent's reasoning token-by-token during WhatsApp message processing.

```
[WhatsApp User] → Evolution API → POST /api/v1/webhooks/evolution
                                      ↓
                              whatsapp_consumer._try_process_with_agent()
                                      ↓
                              agents/agent_executor.py.process_message()
                                      ↓ emit thinking_start
                              realtime_event_bus.publish() → Redis pub/sub
                                      ↓
                              agents/graph/nodes.generate_response_node()
                                      ↓
                              inference_service.astream_chat_completion_with_thinking()
                                      ↓ (streaming SSE from LM Studio)
                              <think> parser state machine
                                      ↓ per token
                              realtime_event_bus.publish(thinking_token) → Redis
                                      ↓
                              socket_service.py (Redis subscriber) → socket.io emit
                                      ↓
                              Frontend socketService.ts (thinking_event handler)
                                      ↓
                              useChatStore.appendThinkingToken()
                                      ↓
                              ThinkingManager → ThinkingBubble renders tokens
```

## LM Studio Integration

- **Protocol:** OpenAI-compatible HTTP API (`POST /v1/chat/completions`)
- **Streaming:** SSE (Server-Sent Events) with `stream: true`
- **Thinking models:** Qwen3.5 variants emit `<think>...</think>` blocks before the main response
- **Non-thinking models:** Stream all content as response tokens (no thinking blocks)

## Frontend State Machine (ThinkingBubble)

```
idle ──[thinking_start]──→ indicator (ThinkingIndicator component)
                                ↓
                        [thinking_token] → streaming (ThinkingBubble component)
                                ↓              ↓
                         [thinking_end]   [more tokens]
                                ↓
                           collapsed (ThinkingCollapsed component)
                                ↓
                         [5s timeout / clearThinking]
                                ↓
                              idle
```

State lives in `useChatStore.thinkingEvents` keyed by `conversationId`.

## Key Invariants

1. `thinking_token` events are ignored when state is `idle` or `collapsed`
2. `appendThinkingToken()` automatically transitions `indicator → streaming`
3. Each ThinkingBubble is scoped to a single `conversationId`
4. The response stored in agent state is only the content AFTER `</think>` (not the thinking reasoning)
5. Backend runs locally (not in Docker) to access `localhost:1234` LM Studio directly
