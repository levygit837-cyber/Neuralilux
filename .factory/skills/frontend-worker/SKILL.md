---
name: frontend-worker
description: TypeScript/React/Next.js frontend worker for ThinkingBubble, stores, and socket service fixes
---

# Frontend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

- Changes to `frontend/src/components/chat/ThinkingManager.tsx`
- Changes to `frontend/src/components/chat/ThinkingBubble.tsx`
- Changes to `frontend/src/services/socketService.ts`
- Changes to `frontend/src/stores/useChatStore.ts`
- Any TypeScript/React frontend work in this project

## Required Skills

`agent-browser` — use to verify ThinkingBubble UI state transitions visually after implementing fixes.

## Work Procedure

1. **Read all relevant files before writing any code.** Read the component, its store, its types, and the socket service handler. The state machine is: `idle → indicator → streaming → collapsed → idle`.

2. **Implement the fixes.** Be surgical — change only what the feature description specifies. Do not refactor unrelated code.

3. **Type-check immediately after each change:**
   ```bash
   cd /home/levybonito/Projetos/Neuralilux/frontend && npx tsc --noEmit
   ```
   Fix all type errors before proceeding.

4. **Verify the frontend is still running** at `localhost:3000`:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
   # expect 200 or 307
   ```
   If not running, do NOT restart it — return to orchestrator.

5. **Use `agent-browser` for interactive verification.** Navigate to `http://localhost:3000`. The page redirects to `/login` — use test credentials if needed, or use evaluate to directly call store actions to simulate thinking events.

6. **To simulate thinking events from the browser console** (for testing without a real WhatsApp message):
   ```javascript
   // Inject a thinking flow via store directly:
   const store = window.__NEXT_DATA__ // won't work directly
   // Use agent-browser evaluate to call store actions:
   // This tests the UI state machine in isolation
   ```

7. **Verify each bug fix explicitly:**
   - **Bug 1 (handleExpand summary):** After a full thinking cycle, click Recolher → Expandir → Recolher again. Verify summary is identical both times.
   - **Bug 2 (auto-clear cancel):** After thinking_end, click Expandir within 5s. Verify component is still visible after 6s.

## Example Handoff

```json
{
  "salientSummary": "Fixed handleExpand to preserve summary in ThinkingManager.tsx (passed thinkingEvent.summary as 3rd arg). Added timer ref to socketService to cancel auto-clear on user expand. TypeScript compiles cleanly. Verified both bug fixes via agent-browser.",
  "whatWasImplemented": "1) ThinkingManager.tsx handleExpand now calls setThinkingState(conversationId, 'streaming', thinkingEvent.summary) instead of omitting the summary arg. 2) socketService.ts now stores the clearTimeout ref per conversationId in a Map<string, ReturnType<typeof setTimeout>> and exposes cancelClearTimer() via useChatStore; ThinkingManager.tsx calls cancelClearTimer on expand. TypeScript compiles with 0 errors.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {
        "command": "cd /home/levybonito/Projetos/Neuralilux/frontend && npx tsc --noEmit",
        "exitCode": 0,
        "observation": "0 type errors"
      },
      {
        "command": "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000",
        "exitCode": 0,
        "observation": "307 (redirect to /login, frontend running)"
      }
    ],
    "interactiveChecks": [
      {
        "action": "Navigate to /chat, simulate thinking_end via store evaluate, click Recolher, click Expandir, click Recolher again",
        "observed": "Summary 'Analisando a intenção do usuário...' visible identically in both ThinkingCollapsed renders"
      },
      {
        "action": "Simulate thinking_end, click Expandir within 2s, wait 7s",
        "observed": "ThinkingBubble still visible after 7s — timer successfully cancelled"
      }
    ]
  },
  "tests": {
    "added": []
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- Frontend is not running and cannot be started (port conflict or build error)
- ThinkingBubble state machine has deeper architectural issues beyond the specified bugs
- Backend-side changes are needed to verify the feature (out of scope for this skill)
