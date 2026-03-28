# User Testing

Testing surface, validation tools, and resource cost classification.

---

## Validation Surface

### Surface 1: Dashboard Web UI (`localhost:3000`)
- **Tool:** `agent-browser`
- **Entry point:** `http://localhost:3000` (redirects to `/login`)
- **Relevant page:** `/chat` — WhatsApp conversations with ThinkingBubble
- **Auth:** Required. Test credentials TBD (check `backend/scripts/seed_data.py` or create via API)
- **Setup needed:** Backend must be running at `localhost:8000`, frontend at `localhost:3000`
- **Thinking events:** Triggered by simulating a WhatsApp webhook (see AGENTS.md Testing section)

### Surface 2: Backend API (`localhost:8000`)
- **Tool:** `curl`
- **Key endpoints:**
  - `POST /api/v1/webhooks/evolution` — simulate WhatsApp message
  - `GET /api/v1/agents/health` — LM Studio connectivity check
  - `POST /api/v1/agents/chat` — Super agent direct chat
- **Auth:** Bearer token or session cookie for protected endpoints
- **No auth needed:** Webhook endpoint (Evolution API calls it directly)

### Surface 3: Backend Unit Tests
- **Tool:** `pytest`
- **Command:** `source backend/venv/bin/activate && cd backend && python -m pytest tests/ -v`
- **Scope:** `tests/test_inference_streaming.py`, `tests/test_thinking_events.py`

---

## Validation Concurrency

**Machine specs:** 
- RAM: ~16GB total, ~10GB available
- CPU: 8+ cores
- LM Studio running and consuming ~1-2GB RAM

**Surface 1 (agent-browser):** Each browser instance ~300MB + frontend already running (~200MB already counted). Estimated headroom: ~8GB usable. At 300MB per validator: max 5, but LM Studio inference is serial (one request at a time), so parallel browser tests may queue on inference. **Max concurrent: 2**

**Surface 2 (curl):** Negligible resource cost. **Max concurrent: 5**

**Surface 3 (pytest):** Unit tests mock LM Studio, lightweight. **Max concurrent: 4**

---

## Testing Gotchas

### Triggering ThinkingBubble in Browser Tests

The ThinkingBubble only appears when:
1. A real WhatsApp message is processed by the agent (via webhook)
2. The dashboard is connected to socket.io and watching the right conversation

To trigger thinking events in browser tests:
```bash
# Step 1: Start backend
./start-backend.sh &
sleep 5

# Step 2: Ensure frontend is connected to backend socket.io
# (happens automatically when /chat page loads)

# Step 3: Send webhook
curl -X POST http://localhost:8000/api/v1/webhooks/evolution \
  -H 'Content-Type: application/json' \
  -d '{"event":"messages.upsert","instance":"INSTANCE_NAME","data":{"key":{"remoteJid":"5511999999999@s.whatsapp.net","fromMe":false,"id":"test-001"},"message":{"conversation":"Olá"},"messageType":"conversation","messageTimestamp":1234567890}}'
```

Replace `INSTANCE_NAME` with the actual Evolution API instance name configured in the system.

### Auth for Dashboard

The `/chat` page requires authentication. Workers should:
1. Check `backend/scripts/seed_data.py` for default test credentials
2. Or create a user via `POST /api/v1/auth/register`
3. Or check `.env` for any SUPERUSER credentials

### LM Studio Response Time

Qwen3.5-4b at 4B parameters on CPU can take 10-30 seconds for a response. Browser tests that wait for `thinking_end` should use a timeout of at least 60s. The ThinkingIndicator should remain visible during this time (VAL-CROSS-004).

### Redis Events for Debugging

Monitor Redis pub/sub to see thinking events in real-time:
```bash
docker exec -it neuralilux-redis redis-cli -a redis_password SUBSCRIBE neuralilux:realtime:events
```

### Conversation Room Joining

The frontend joins `conversation:{instance}:{conversationId}` socket.io room after loading messages. Thinking events are also emitted to `instance:{instance}` room as fallback. Make sure the test conversation is loaded/selected in the dashboard before sending the webhook.
