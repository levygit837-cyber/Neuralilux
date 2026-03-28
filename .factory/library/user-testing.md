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

---

## Flow Validator Guidance: agent-browser

### Isolation Rules for Dashboard UI Tests

**Shared Infrastructure (DO NOT TOUCH):**
- LM Studio at localhost:1234 (already running, do not reconfigure)
- Docker containers (postgres, redis, rabbitmq, evolution)
- Backend at localhost:8000 (do not restart)
- Frontend at localhost:3000 (already running, do not restart)

**Isolation Boundary:**
Each flow validator gets:
- A dedicated browser session
- A dedicated test conversation (unique phone number/JID)
- Unique test message IDs to avoid collisions

**Naming Convention for Test Data:**
- Phone numbers: Use pattern `55119{validator_id}{sequence}@s.whatsapp.net`
- Message IDs: Use pattern `test-{validator_id}-{timestamp}-{sequence}`
- Instance name: Use "Whatsapp" (the connected test instance)

**State Mutation Rules:**
- DO NOT click "Recolher" or "Expandir" on thinking components that belong to other validators
- DO NOT send webhooks to the same conversationId simultaneously from different validators
- OK to navigate between pages, login, logout
- OK to create new conversations (they're isolated by phone number)

**Resource Limits:**
- Max 2 concurrent browser validators (per user-testing.md Validation Concurrency)
- Each browser ~300MB RAM

---

## Flow Validator Guidance: curl

### Isolation Rules for API Tests

**Shared Infrastructure:**
- Backend API at localhost:8000
- LM Studio at localhost:1234
- Redis, PostgreSQL via Docker

**Isolation Boundary:**
- No special isolation needed - API calls are stateless or use unique IDs
- Use unique test message IDs: `test-{validator_id}-{timestamp}`
- Use unique phone numbers: `55119{validator_id}999@s.whatsapp.net`

**State Mutation Rules:**
- OK to query any endpoint (GET requests are safe)
- OK to POST to webhook endpoint (creates new messages, no collision if IDs unique)
- DO NOT run database migrations
- DO NOT restart services

**Resource Limits:**
- Max 5 concurrent curl validators
- Negligible resource cost per validator

---

## Flow Validator Guidance: pytest

### Isolation Rules for Unit Tests

**Shared Infrastructure:**
- Backend codebase at /home/levybonito/Projetos/Neuralilux/backend
- Python venv at backend/venv/

**Isolation Boundary:**
- Unit tests mock external services (LM Studio)
- No real network calls
- Tests run in separate process via pytest

**State Mutation Rules:**
- DO NOT modify source code
- DO NOT install new packages
- OK to create test fixtures if needed
- Tests should use mocks, not real services

**Resource Limits:**
- Max 4 concurrent pytest validators
- Lightweight - only Python process overhead

**Test Commands:**
```bash
cd /home/levybonito/Projetos/Neuralilux/backend
source venv/bin/activate
python -m pytest tests/test_inference_streaming.py -v
python -m pytest tests/test_thinking_events.py -v
```
