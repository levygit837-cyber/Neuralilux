---
name: backend-worker
description: Python/FastAPI backend worker for inference service, LangGraph nodes, and realtime event emission
---

# Backend Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the WORK PROCEDURE.

## When to Use This Skill

- Changes to `backend/app/services/inference_service.py`
- Changes to `backend/app/agents/graph/nodes.py` or `backend/app/super_agents/graph/nodes.py`
- Changes to `backend/.env` or `start-backend.sh`
- Any Python/FastAPI backend work involving LM Studio, streaming, or realtime events

## Required Skills

None. All verification is done via pytest and curl.

## Work Procedure

1. **Read all relevant files before writing any code.** At minimum: the file you're changing, its imports, and any files it calls into. Do NOT guess at API signatures — read the actual code.

2. **Write unit tests FIRST (TDD — red before green).**
   - Test file location: `backend/tests/test_<feature_name>.py`
   - Run tests to confirm they FAIL before implementing: `source backend/venv/bin/activate && cd backend && python -m pytest tests/test_<feature>.py -v`
   - Tests must be specific: mock httpx/requests where needed, test each state transition, test error cases.

3. **Implement the feature** to make tests pass (green).
   - Run tests again: `python -m pytest tests/test_<feature>.py -v` — all must pass.

4. **Run the full test suite** to check for regressions:
   ```bash
   source backend/venv/bin/activate && cd backend && python -m pytest tests/ -v
   ```

5. **Start the backend and verify manually:**
   ```bash
   cd /home/levybonito/Projetos/Neuralilux && ./start-backend.sh &
   sleep 5
   curl -s http://localhost:8000/health || curl -s http://localhost:8000/docs | head -5
   ```

6. **For streaming/event features:** Test with a real LM Studio call:
   ```bash
   # Test streaming directly against LM Studio
   curl -s -X POST http://localhost:1234/v1/chat/completions \
     -H 'Content-Type: application/json' \
     -d '{"model":"qwen3.5-4b","messages":[{"role":"user","content":"think: what is 2+2?"}],"stream":true}' \
     --no-buffer | head -20
   ```

7. **For webhook/event features:** Simulate a WhatsApp webhook and watch logs:
   ```bash
   curl -X POST http://localhost:8000/api/v1/webhooks/evolution \
     -H 'Content-Type: application/json' \
     -d '{"event":"messages.upsert","instance":"test","data":{"key":{"remoteJid":"5511@s.whatsapp.net","fromMe":false,"id":"t1"},"message":{"conversation":"teste"},"messageType":"conversation","messageTimestamp":1234567890}}'
   ```
   Check logs for `thinking_token` events being published.

8. **Kill backend after testing:**
   ```bash
   lsof -ti :8000 | xargs kill -9 2>/dev/null || true
   ```

## Example Handoff

```json
{
  "salientSummary": "Added astream_chat_completion_with_thinking() to inference_service.py with full <think> state machine; 8 unit tests passing including split-tag scenarios. Verified real streaming against qwen3.5-4b at localhost:1234 returns thinking tokens.",
  "whatWasImplemented": "New async generator method astream_chat_completion_with_thinking() in InferenceService using httpx streaming. State machine tracks in_think/outside_think with partial-tag buffer for split-boundary tags. Yields ('thinking', str) and ('response', str) tuples. Added 8 unit tests in tests/test_inference_streaming.py covering: normal think block, no think block, split open tag, split close tag, empty stream, [DONE]-only, LM Studio error handling, and fallback mode.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {
        "command": "python -m pytest tests/test_inference_streaming.py -v",
        "exitCode": 0,
        "observation": "8 passed in 0.43s — all state machine scenarios covered"
      },
      {
        "command": "python -m pytest tests/ -v",
        "exitCode": 0,
        "observation": "22 passed, 0 failed — no regressions"
      },
      {
        "command": "curl -s -X POST http://localhost:1234/v1/chat/completions -H 'Content-Type: application/json' -d '{\"model\":\"qwen3.5-4b\",\"messages\":[{\"role\":\"user\",\"content\":\"think step by step: 3+3?\"}],\"stream\":true}' --no-buffer | head -10",
        "exitCode": 0,
        "observation": "SSE chunks received starting with data: {\"choices\":[{\"delta\":{\"content\":\"<think>\"}...}]}"
      }
    ],
    "interactiveChecks": []
  },
  "tests": {
    "added": [
      {
        "file": "backend/tests/test_inference_streaming.py",
        "cases": [
          { "name": "test_stream_uses_stream_true", "verifies": "VAL-BE-001" },
          { "name": "test_parse_think_block_normal", "verifies": "VAL-BE-003 + VAL-BE-004" },
          { "name": "test_response_after_think", "verifies": "VAL-BE-005" },
          { "name": "test_split_open_tag", "verifies": "VAL-BE-007" },
          { "name": "test_split_close_tag", "verifies": "VAL-BE-007" },
          { "name": "test_no_think_fallback", "verifies": "VAL-BE-006" },
          { "name": "test_done_sentinel_terminates", "verifies": "VAL-BE-002" },
          { "name": "test_lm_studio_error_handling", "verifies": "VAL-BE-010" }
        ]
      }
    ]
  },
  "discoveredIssues": []
}
```

## When to Return to Orchestrator

- LM Studio is not responding and cannot be reached (external dependency)
- `realtime_event_bus.publish()` fails due to Redis connection issues not related to this feature
- LangGraph state schema incompatibilities that require broader architectural changes
- Test failures caused by pre-existing bugs in unrelated modules
