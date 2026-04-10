# Environment

Environment variables, external dependencies, and setup notes.

**What belongs here:** Required env vars, external services, dependency quirks, platform-specific notes.
**What does NOT belong here:** Service ports/commands (use `.factory/services.yaml`).

---

## Backend Environment Variables

Defined in `backend/.env` (overridable via `start-backend.sh` exports):

| Variable | Value (after fix) | Notes |
|----------|------------------|-------|
| `LM_STUDIO_URL` | `http://localhost:1234` | ⚠ Was `http://172.17.0.1:1235` — fixed in feature 1 |
| `LM_STUDIO_MODEL` | `qwen3.5-4b` | Changed from `nvidia/nemotron-3-nano-4b` in feature 1 |
| `LM_STUDIO_DISABLE_THINKING` | `false` | Changed from `true` in feature 1 |
| `LM_STUDIO_MAX_TOKENS` | `2048` | |
| `LM_STUDIO_TEMPERATURE` | `0.7` | |
| `DATABASE_URL` | see backend/.env | Docker Postgres at localhost:5434 |
| `REDIS_URL` | see backend/.env | Docker Redis at localhost:6380 |
| `RABBITMQ_URL` | see backend/.env | Docker RabbitMQ at localhost:5672 |
| `EVOLUTION_API_URL` | `http://localhost:8081` | |
| `EVOLUTION_API_KEY` | see backend/.env | |
| `SECRET_KEY` | (see .env) | JWT signing |

## Frontend Environment Variables

Defined in `frontend/.env.local` or Next.js defaults:

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API |
| `NEXT_PUBLIC_WS_URL` | `ws://localhost:8000` | Socket.io |

## Python Dependencies (key ones)

- `httpx==0.26.0` — async HTTP client for LM Studio streaming (already installed)
- `python-socketio[asyncio]` — socket.io server
- `redis[asyncio]` — Redis pub/sub for realtime events
- `langgraph` — agent graph execution
- `fastapi` — REST API framework
- `uvicorn` — ASGI server

## Why Backend Runs Locally (not Docker)

LM Studio runs on `localhost:1234` on the host machine. When the backend ran in Docker, it had to use the Docker bridge IP (`172.17.0.1`) to reach LM Studio on the host. The project was simplified by moving the backend to run directly on the host, so it can use `localhost:1234` directly.

## LM Studio Models Available

| Model | Thinking Support | Size | Use Case |
|-------|-----------------|------|----------|
| `qwen3.5-4b` | ✓ YES | ~4B params | **Recommended** — thinking + good quality |
| `qwen3.5-2b-claude-4.6-opus-reasoning-distilled` | ✓ YES | ~2B params | Lighter, less quality |
| `qwen3.5-4b-claude-4.6-opus-reasoning-distilled-v2` | ✓ YES | ~4B params | Alternative 4B |
| `qwen/qwen3.5-9b` | ✓ YES | ~9B params | Higher quality, slower |
| `nvidia/nemotron-3-nano-4b` | ✗ NO | ~4B params | No thinking blocks |
| Embedding models | N/A | - | Text embeddings only |
