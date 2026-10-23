# Neuralilux: guia para agentes

Agente de atendimento por WhatsApp com IA (FastAPI + Next.js + Evolution API). Vocabulário do domínio em `CONTEXT.md`; decisões em `docs/adr/`.

## Layout

- `backend/`: FastAPI, SQLAlchemy, Alembic, consumer RabbitMQ. `app/{agent,api,core,llm,models,packs,realtime,schemas,services,whatsapp}`; worker em `scripts/run_worker.py`.
- `frontend/`: Next.js 16 / React 19 (tem seu próprio `frontend/AGENTS.md`).
- `docs/`: `setup.md`, `architecture.md`, `agent.md`, `packs.md`, `integrations.md`, `operations.md`; `adr/` (decisões) e `agents/` (guias para agentes). Índice no `README.md` da raiz.
- `docker-compose.example.yml`: modelo versionado da infra local, sem segredos. O `docker-compose.yml` real é local e ignorado.

## Comandos

- Testes backend: `cd backend && rm -f test.db && env -u DATABASE_URL ./venv/bin/python -m pytest tests --ignore=tests/e2e -q -n auto; rm -f test.db` (paralelo com pytest-xdist; ~25 s. O bcrypt usa custo 4 só nos testes, em `tests/conftest.py`; produção segue em 12)
- Infra local: `cp docker-compose.example.yml docker-compose.yml && docker compose --env-file backend/.env up -d` (precisa de `EVOLUTION_API_KEY` e `EVOLUTION_WEBHOOK_TOKEN` no `backend/.env`).
- Migrações: `cd backend && ./venv/bin/alembic upgrade head` (cadeia fixa em `docs/agents/migrations.md`).
- Seed de dev: `cd backend && SEED_DEV_SUPERUSER=1 ./venv/bin/python scripts/seed_data.py`.
- API e worker: `cd backend && ./venv/bin/uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload` e `./venv/bin/python scripts/run_worker.py`.
- Re-criptografar chaves de Gateway (HKDF): `cd backend && ./venv/bin/python scripts/reencrypt_gateway_secrets.py`. Passo único obrigatório ao atualizar um banco existente, antes de subir a app; idempotente.
- Criar/promover superusuário (só superuser edita Gateways): `cd backend && SUPERUSER_EMAIL=... SUPERUSER_PASSWORD=... ./venv/bin/python scripts/create_superuser.py`. Em dev, `SEED_DEV_SUPERUSER=1` no `seed_data.py` promove o usuário de teste.
- Frontend: `cd frontend && npx eslint . && npx tsc --noEmit && npx next build`
- Instalar deps Python: `PIP_CONFIG_FILE=/dev/null ./venv/bin/pip install --index-url https://pypi.org/simple -r requirements-dev.txt` (`requirements.txt` é só runtime, o que vai para a imagem; `requirements-dev.txt` inclui ele mais pytest, lint e tipos).

## Regras

- Dependências com versão exata (`==`).
- Nunca commitar `backend/.env`, `docker-compose.yml` ou `design/` (ignorados).
- Toda mudança entra por PR revisado; nunca push direto em `main`.
- Testes rodam em SQLite; e2e só com `RUN_E2E=1`.
- Código do núcleo (`backend/app/agent/`) não conhece nenhum ramo de negócio; o que é de um ramo vive num Pack (ADR 0004).

## Agent skills

### Issue tracker

Issues e PRDs ficam no GitHub Issues de `levygit837-cyber/Neuralilux`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Os cinco papéis canônicos com os nomes default (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` e `docs/adr/` na raiz. See `docs/agents/domain.md`.
