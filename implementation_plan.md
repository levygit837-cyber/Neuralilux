# Implementation Plan

[Overview]
Implement a unified tool-execution observability layer that makes backend tool usage explicit, exposes real tool results to the frontend, and adds realtime tool lifecycle events for both the Super Agent and the WhatsApp agent without changing business behavior first.

The current codebase already has two distinct agent paths. The Super Agent classifies intent, runs `execute_tools_for_state()` in `backend/app/super_agents/tool_runtime.py`, persists `tool_calls` as `role="tool"` records, and then either returns a direct backend-crafted answer or asks the model to write the final response from tool context. The WhatsApp agent uses deterministic tool invocations inside `backend/app/agents/graph/nodes.py` and emits only thinking/response streaming events. In both flows, the model is not performing native provider-level tool calling; the backend is deciding when tools run and then passing the results to the model or returning a direct answer. This means the system does use tools, but not through the model’s own provider-native `tool_calls` protocol.

The frontend only visualizes `thinking_event` activity today. `frontend/src/services/socketService.ts` listens for `thinking_event`, `response_start`, and `response_token`, while `frontend/src/components/agent/AgentChat.tsx` and `frontend/src/components/chat/ThinkingManager.tsx` render thinking states. There is no dedicated `tool_event` socket event, no timeline/card UI for tool execution, and no rendering of persisted `role="tool"` history in `AgentChat`. Although `backend/app/super_agents/agent_executor.py` stores tool messages and `backend/app/api/v1/endpoints/agents.py` can return `tool_name`, `tool_input`, and `tool_output` in session history, the frontend types and render pipeline currently ignore them.

This implementation should therefore focus on three concrete outcomes: first, make current tool execution visible and auditable in realtime; second, surface structured tool results and historical tool usage in the frontend; third, improve correctness by making the current orchestration path transparent and testable before any later migration to true native LLM tool calling. A later phase can replace heuristic routing with native provider or LangGraph tool nodes, but that should be deferred until telemetry proves the current execution path and UX are stable.

[Types]
Define shared backend and frontend tool telemetry contracts and extend existing chat payload types so live tool execution, persisted tool messages, and request-scoped tool traces become first-class data.

Detailed type definitions, interfaces, validation rules, and relationships:

- Backend type alias: `ToolEventPhase = Literal["waiting_input", "started", "completed", "failed"]`
  - `waiting_input`: the backend identified a tool-driven workflow but is blocked on explicit user confirmation or disambiguation.
  - `started`: a concrete tool/helper invocation is about to run.
  - `completed`: the tool/helper invocation finished successfully.
  - `failed`: the tool/helper invocation raised an exception or returned an explicit error payload.

- Backend type alias: `ToolEventSource = Literal["super_agent", "whatsapp_agent"]`
  - `super_agent` for `backend/app/super_agents/*`.
  - `whatsapp_agent` for `backend/app/agents/*`.

- Backend payload model: `ToolExecutionEventPayload`
  - `trace_id: str`
    - Required.
    - Stable identifier for one logical tool execution within a request.
  - `request_id: str`
    - Required.
    - Groups all tool executions triggered by one user message.
  - `source: ToolEventSource`
    - Required.
  - `tool_name: str`
    - Required.
    - Must match persisted `tool_calls[].name` and/or `SuperAgentMessage.tool_name`.
  - `phase: ToolEventPhase`
    - Required.
  - `conversation_id: str`
    - Required for socket fan-out and frontend state keys.
    - For Super Agent, use the session ID already routed through `agent_chat:{session_id}`.
    - For WhatsApp chat, use the active `conversation_id` or remote JID.
  - `session_id: str | None`
    - Optional for WhatsApp agent, required for Super Agent.
  - `instance_name: str`
    - Required because `ChatSocketService.emit_realtime_event()` routes by instance room first.
  - `display_name: str | None`
    - Optional human-readable label for the UI.
  - `input_payload: dict[str, Any] | None`
    - Optional raw structured input.
    - Must be JSON-serializable before socket emission.
  - `input_preview: str | None`
    - Optional truncated preview for UI cards.
  - `output_payload: Any | None`
    - Optional raw structured result.
    - May be omitted from socket payload when configuration disables raw payload broadcast.
  - `output_preview: str | None`
    - Optional truncated preview for UI cards and debugging.
  - `error: str | None`
    - Required when `phase == "failed"`.
  - `started_at: str | None`
    - ISO-8601 timestamp for `started`, `completed`, and `failed` phases.
  - `finished_at: str | None`
    - ISO-8601 timestamp for `completed` and `failed` phases.

- Backend API schema: `ToolCallResponse`
  - Add in `backend/app/schemas/super_agent.py`.
  - Fields: `name: str`, `input: dict[str, Any] | None`, `output: Any | None`, `status: Literal["completed", "failed"]`, `trace_id: str | None`, `started_at: datetime | None`, `finished_at: datetime | None`.
  - Used by `AgentChatResponse` and `SuperAgentChatResponse` so the immediate HTTP reply reflects actual backend tool usage.

- Frontend type: `ToolExecutionPhase`
  - TS union mirroring backend phases.

- Frontend type: `ToolExecutionEvent`
  - Mirror of `ToolExecutionEventPayload` with `startedAt` and `finishedAt` camelCase aliases if preferred by the UI.
  - Used in socket listeners, local component state, and `useChatStore`.

- Frontend type: `ToolExecutionTrace`
  - `traceId: string`
  - `requestId: string`
  - `toolName: string`
  - `displayName?: string`
  - `phase: ToolExecutionPhase`
  - `inputPreview?: string`
  - `outputPreview?: string`
  - `error?: string`
  - `startedAt?: Date`
  - `finishedAt?: Date`
  - Represents the latest UI-facing state for one tool execution.

- Extend `frontend/src/types/agent.ts`
  - `AgentMessageBlockType` should include `'tool_execution'`.
  - `AgentSessionMessage` must add:
    - `tool_name?: string | null`
    - `tool_input?: Record<string, unknown> | null`
    - `tool_output?: string | null`
    - `metadata?: Record<string, unknown> | null`
  - `AgentMessage` should add:
    - `toolTrace?: ToolExecutionTrace`
    - `toolEvents?: ToolExecutionTrace[]`
  - Immediate send response type should add `tool_calls?: ToolCallResponse[]`.

- Extend `frontend/src/types/chat.ts`
  - Add `toolTraces?: Record<string, ToolExecutionTrace[]>` to support WhatsApp chat view state keyed by conversation ID.
  - Existing `ThinkingEvent` remains separate from tool telemetry to avoid conflating reasoning with concrete tool execution.

Validation rules:

- Every emitted tool event must include `tool_name`, `phase`, `trace_id`, `request_id`, and a stable conversation key.
- `waiting_input` must never include `output_payload`.
- `failed` must always include a non-empty `error` string.
- Socket payloads must remain JSON-safe and must not expose raw payloads larger than the configured preview size unless an explicit backend flag allows it.

[Files]
Add a shared tool telemetry backend and frontend surface, extend existing agent/chat payloads, and wire new UI components into both chat experiences.

Detailed breakdown:

- New files to be created
  - `backend/app/services/tool_event_service.py`
    - Central helper to build, normalize, and publish `tool_event` payloads to `realtime_event_bus`.
    - Responsible for preview truncation, JSON-safe serialization, trace/request ID handling, and source tagging.
  - `backend/tests/test_socket_tool_events.py`
    - Focused pytest coverage for `ChatSocketService.emit_realtime_event()` when `event_type == "tool_event"`.
  - `frontend/src/types/toolEvents.ts`
    - Shared TS definitions for live tool events and normalized tool traces.
  - `frontend/src/components/tooling/ToolExecutionCard.tsx`
    - Reusable visual card for one tool execution, including phase badge, previews, and error state.
  - `frontend/src/components/tooling/ToolExecutionTimeline.tsx`
    - Reusable live timeline/list component for current request and persisted history.

- Existing files to be modified
  - `backend/app/core/config.py`
    - Add flags such as preview length and whether raw tool payloads are allowed in realtime events.
  - `backend/.env.example`
    - Document any new tool telemetry environment flags.
  - `backend/app/services/socket_service.py`
    - Add `tool_event` normalization and room fan-out alongside the existing `thinking` handling.
  - `backend/app/super_agents/tool_runtime.py`
    - Instrument all tool-capable branches (`web`, `whatsapp`, `knowledge`, `document`, `menu`, `database`) and all pending-action states.
  - `backend/app/super_agents/state.py`
    - Add `request_id` and optional in-flight tool trace metadata to the state contract.
  - `backend/app/super_agents/graph/super_agent_graph.py`
    - Seed `request_id` and any new tool telemetry state fields in the initial state.
  - `backend/app/super_agents/graph/nodes.py`
    - Thread `request_id` through node execution and guarantee tool metadata survives into the final state/response.
  - `backend/app/super_agents/agent_executor.py`
    - Return enriched `tool_calls` in the public result and persist any new trace metadata if needed.
  - `backend/app/schemas/super_agent.py`
    - Add `ToolCallResponse` and extend chat response schemas.
  - `backend/app/api/v1/endpoints/agents.py`
    - Serialize `tool_calls` in `/api/v1/agents/chat` and related Super Agent endpoints.
  - `backend/app/agents/graph/nodes.py`
    - Emit tool events for deterministic WhatsApp-agent tool execution paths such as `cardapio_tool`, `pedido_tool`, and related direct-action helpers.
  - `backend/unit_tests/test_super_agent_tools_runtime.py`
    - Add assertions for emitted telemetry, trace grouping, and richer `tool_calls` metadata.
  - `backend/tests/test_socket_thinking_events.py`
    - Extend normalization coverage so `thinking_event` and `tool_event` contracts remain aligned.
  - `backend/tests/test_realtime_bridge.py`
    - Add or extend integration coverage for WhatsApp-agent-side tool telemetry, not only incoming-message bridge events.
  - `frontend/src/services/socketService.ts`
    - Listen for `tool_event`, normalize payloads, update stores/callbacks, and expose agent-chat tool event subscription hooks.
  - `frontend/src/services/agentService.ts`
    - Type the richer `sendMessage()` and `getSessionMessages()` payloads.
  - `frontend/src/types/agent.ts`
    - Add tool-related message fields and new block types.
  - `frontend/src/types/chat.ts`
    - Add chat-level tool trace state definitions.
  - `frontend/src/stores/useChatStore.ts`
    - Track tool traces per conversation and add actions for upsert/complete/fail/clear.
  - `frontend/src/components/agent/AgentChat.tsx`
    - Render live tool execution timeline, surface persisted role=`tool` history, and keep tool UI aligned with thinking/response streaming.
  - `frontend/src/components/agent/AgentMessage.tsx`
    - Render `tool_execution` blocks using the new reusable tool card component.
  - `frontend/src/components/chat/WhatsAppChat.tsx`
    - Render conversation-level tool telemetry under the active message list.
  - `frontend/src/components/chat/ThinkingManager.tsx`
    - Ensure tool timeline ordering works cleanly with existing thinking UI when both are visible.

- Files to be deleted or moved
  - No deletions or moves are required.

- Configuration file updates
  - `backend/app/core/config.py`
    - Add `TOOL_EVENT_PREVIEW_LIMIT: int`.
    - Add `TOOL_EVENT_INCLUDE_RAW_PAYLOADS: bool`.
  - `backend/.env.example`
    - Document both new settings so production can choose safe/default socket payload sizes.

[Functions]
Introduce a shared tool event emitter, instrument existing tool orchestration points, and extend frontend listeners/render helpers so both realtime and persisted tool usage become visible.

Detailed breakdown:

- New functions
  - `emit_tool_event(*, source: str, tool_name: str, phase: str, instance_name: str, conversation_id: str, request_id: str, trace_id: str, session_id: str | None = None, input_payload: dict[str, Any] | None = None, output_payload: Any | None = None, error: str | None = None, display_name: str | None = None) -> Awaitable[None]`
    - File: `backend/app/services/tool_event_service.py`
    - Purpose: single backend entry point for `tool_event` realtime emission.
  - `build_tool_preview(payload: Any, limit: int) -> str | None`
    - File: `backend/app/services/tool_event_service.py`
    - Purpose: convert structured input/output into safe UI-friendly previews.
  - `normalizeToolEvent(payload: unknown): ToolExecutionEvent | null`
    - File: `frontend/src/services/socketService.ts`
    - Purpose: validate and normalize socket payloads before UI/state usage.
  - `setAgentToolEventCallback(callback: ((event: ToolExecutionEvent) => void) | null): void`
    - File: `frontend/src/services/socketService.ts`
    - Purpose: give `AgentChat` a dedicated realtime tool-event channel, parallel to thinking callbacks.
  - `upsertToolTrace(conversationId: string, event: ToolExecutionEvent): void`
    - File: `frontend/src/stores/useChatStore.ts`
    - Purpose: maintain latest tool execution state for WhatsApp chat.
  - `clearToolTraces(conversationId: string): void`
    - File: `frontend/src/stores/useChatStore.ts`
    - Purpose: reset old tool traces when switching chats or after request completion.
  - `buildToolHistoryBlocks(items: AgentSessionMessage[]): AgentMessage[]`
    - File: `frontend/src/components/agent/AgentChat.tsx`
    - Purpose: convert persisted role=`tool` messages into `tool_execution` UI blocks.
  - `handleToolEvent(event: ToolExecutionEvent): void`
    - File: `frontend/src/components/agent/AgentChat.tsx`
    - Purpose: attach live tool events to the current request timeline.

- Modified functions
  - `_add_tool_call(tool_calls, name, tool_input, tool_output)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: accept optional status/trace/timestamp metadata or be replaced by a richer helper so persisted `tool_calls` match emitted telemetry.
  - `execute_tools_for_state(state)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: generate `request_id` fallback, emit `waiting_input`, `started`, `completed`, and `failed`, and preserve trace metadata in the returned state.
  - `_handle_pending_action(...)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: emit `waiting_input` events for confirmation, contact selection, and missing-recipient/missing-message states.
  - `_handle_whatsapp_action(...)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: emit structured events around contact lookup, message reads, single sends, and bulk sends.
  - `_handle_menu_or_database_action(...)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: emit events before and after menu/database execution, including failure paths.
  - `_handle_web_action(...)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: emit explicit web-search/web-fetch telemetry and include SSRF-related failures in `failed` events.
  - `_handle_knowledge_action(...)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: emit store/search telemetry and persist the resulting trace IDs.
  - `_handle_document_action(...)`
    - File: `backend/app/super_agents/tool_runtime.py`
    - Required changes: emit document creation lifecycle events and surface created document metadata.
  - `generate_response_node(state)`
    - File: `backend/app/super_agents/graph/nodes.py`
    - Required changes: guarantee `tool_calls` and `request_id` survive even when `skip_model_response` is true.
  - `run(...)`
    - File: `backend/app/super_agents/graph/super_agent_graph.py`
    - Required changes: seed `request_id` into initial graph state.
  - `process_message(...)`
    - File: `backend/app/super_agents/agent_executor.py`
    - Required changes: return enriched `tool_calls`, not only persist them.
  - `agent_chat(...)`
    - File: `backend/app/api/v1/endpoints/agents.py`
    - Required changes: return `tool_calls` in the immediate response payload.
  - `_serialize_super_agent_message(message)`
    - File: `backend/app/api/v1/endpoints/agents.py`
    - Required changes: keep existing tool fields and ensure frontend-facing metadata remains complete.
  - `_emit_thinking_event(...)`
    - File: `backend/app/agents/graph/nodes.py`
    - Required changes: stay focused on reasoning/response events only; tool lifecycle should move to dedicated tool event emission instead of overloading thinking.
  - `execute_action_node(state)`
    - File: `backend/app/agents/graph/nodes.py`
    - Required changes: wrap deterministic WhatsApp-agent tool invocations with `started`, `completed`, and `failed` tool events.
  - `emit_realtime_event(event)`
    - File: `backend/app/services/socket_service.py`
    - Required changes: normalize and fan out `tool_event` payloads to conversation, agent-chat, and instance rooms.
  - `setupEventListeners()`
    - File: `frontend/src/services/socketService.ts`
    - Required changes: add `socket.on('tool_event', ...)` and forward normalized events to the proper runtime/state consumer.
  - `buildMessagesFromHistory(items)`
    - File: `frontend/src/components/agent/AgentChat.tsx`
    - Required changes: include persisted role=`tool` messages instead of silently ignoring them.
  - `handleSendMessage(content)`
    - File: `frontend/src/components/agent/AgentChat.tsx`
    - Required changes: initialize per-request tool trace state together with thinking/response runtime state.

- Removed functions
  - No function removals are required.
  - If `_add_tool_call()` becomes too limited, keep a compatibility wrapper temporarily and migrate callers incrementally rather than deleting it in the same pass.

[Classes]
Modify the existing socket and executor service classes to support tool telemetry end-to-end; no new OOP-heavy classes are required beyond the existing service architecture.

Detailed breakdown:

- New classes
  - No new classes are required; new behavior should be implemented with helper functions and existing service objects.

- Modified classes
  - `ChatSocketService`
    - File: `backend/app/services/socket_service.py`
    - Specific modifications:
      - Add `tool_event` routing logic in `emit_realtime_event()`.
      - Keep current room strategy (`instance`, `conversation`, `agent_chat`) so tool telemetry reaches both chat UIs.
      - Normalize camelCase/snake_case fields in the emitted payload the same way thinking events are normalized today.
  - `SuperAgentExecutor`
    - File: `backend/app/super_agents/agent_executor.py`
    - Specific modifications:
      - Return enriched `tool_calls` to callers.
      - Preserve `request_id` and trace metadata if needed for debugging and later analytics.
  - `SocketService`
    - File: `frontend/src/services/socketService.ts`
    - Specific modifications:
      - Add dedicated tool-event listener/callback plumbing.
      - Continue handling thinking and response events separately so UI semantics stay clear.

- Removed classes
  - No class removals are required.
  - The current service-based architecture already provides the right extension points.

[Dependencies]
No new external dependencies are required; the implementation should reuse the existing FastAPI, Redis pub/sub, Socket.IO, React, and Zustand stack.

Details of new packages, version changes, and integration requirements:

- Backend
  - Reuse existing `redis.asyncio`, `python-socketio`, and `structlog` packages already present in `backend/requirements.txt`.
  - Reuse the existing `langchain` and `langgraph` stack; no new provider SDK is required for this observability pass.

- Frontend
  - Reuse `socket.io-client`, React state/hooks, and Zustand already present in `frontend/package.json`.
  - Do not add a markdown or inspector dependency just to render tool previews; previews can be rendered with existing JSX and utility helpers.

- Future migration note
  - If native model tool-calling is pursued in a later phase, the existing dependencies are already sufficient to prototype it. That migration should remain behind a feature flag and is intentionally outside the first implementation pass described here.

[Testing]
Cover backend telemetry emission deterministically with pytest, validate frontend typing with TypeScript, and use a manual end-to-end checklist to verify live tool visibility in both chat surfaces.

Test file requirements, existing test modifications, and validation strategies:

- Backend automated tests
  - `backend/tests/test_socket_tool_events.py`
    - Verify `tool_event` fan-out goes to conversation room, agent-chat room, and instance room.
    - Verify payload normalization for `trace_id`, `request_id`, `phase`, previews, and error fields.
  - `backend/unit_tests/test_super_agent_tools_runtime.py`
    - Add assertions that each tool-capable path emits the correct lifecycle sequence.
    - Cover at least:
      - contact resolution / ambiguity
      - confirmation-required send flows
      - successful WhatsApp send
      - successful database/menu lookup
      - successful web search/fetch
      - tool failure path
  - `backend/tests/test_socket_thinking_events.py`
    - Extend or parallelize to ensure `thinking_event` behavior remains unchanged after adding `tool_event`.
  - `backend/tests/test_realtime_bridge.py`
    - Add or extend integration coverage for WhatsApp-agent-side tool telemetry, not only incoming-message bridge events.

- Frontend validation
  - Run `npm run type-check` in `frontend/` after introducing the new telemetry types and block variants.
  - If a frontend test runner is not yet configured, keep this pass focused on type safety plus manual verification rather than introducing a new test framework.

- Manual verification checklist
  - Super Agent: send a prompt that triggers database lookup and confirm a live tool card appears before the final answer.
  - Super Agent: trigger a confirmation-required WhatsApp send and verify a `waiting_input` tool status is visible.
  - Super Agent: trigger a failed web fetch and verify the UI shows `failed` with the error preview.
  - Super Agent history: refresh the page and confirm historical tool messages are rendered, not silently dropped.
  - WhatsApp agent: send a message that triggers deterministic tool logic and confirm tool cards appear in the conversation UI.
  - Ensure existing thinking bubbles still appear and are not replaced by tool cards.
  - Ensure final assistant text still arrives even when one or more tool events were emitted.

[Implementation Order]
Implement the shared telemetry contract first, then instrument backend emitters, then expose richer payloads, and only after that build frontend rendering so the UI can rely on a stable realtime/API contract.

1. Add backend configuration flags and create `backend/app/services/tool_event_service.py` with the canonical tool event builder/emitter.
2. Extend `backend/app/super_agents/state.py` and `backend/app/super_agents/graph/super_agent_graph.py` to seed `request_id` and any trace state needed by the runtime.
3. Instrument `backend/app/super_agents/tool_runtime.py` so every tool path and pending-action path emits structured tool lifecycle events and returns enriched `tool_calls`.
4. Instrument `backend/app/agents/graph/nodes.py` so deterministic WhatsApp-agent tool execution emits the same `tool_event` contract.
5. Extend `backend/app/services/socket_service.py` to route `tool_event` alongside the existing `thinking` event fan-out.
6. Extend `backend/app/schemas/super_agent.py`, `backend/app/super_agents/agent_executor.py`, and `backend/app/api/v1/endpoints/agents.py` so immediate responses and message history expose tool metadata cleanly.
7. Add backend automated tests for socket routing, runtime emission, and regression coverage around existing thinking events.
8. Add frontend telemetry types in `frontend/src/types/toolEvents.ts`, extend `frontend/src/types/agent.ts` and `frontend/src/types/chat.ts`, and update `frontend/src/services/agentService.ts` accordingly.
9. Update `frontend/src/services/socketService.ts` and `frontend/src/stores/useChatStore.ts` to receive, normalize, and store live tool telemetry.
10. Build reusable UI in `frontend/src/components/tooling/ToolExecutionCard.tsx` and `frontend/src/components/tooling/ToolExecutionTimeline.tsx`.
11. Integrate tool timelines into `frontend/src/components/agent/AgentChat.tsx`, `frontend/src/components/agent/AgentMessage.tsx`, and `frontend/src/components/chat/WhatsAppChat.tsx`, ensuring persisted role=`tool` history is rendered.
12. Run backend tests, run frontend type-check, and complete the manual realtime verification checklist in both chat flows before considering any later migration to native model tool-calling.

