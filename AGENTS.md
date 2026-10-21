# Neuralilux: guia para agentes

Agente de atendimento por WhatsApp com IA (FastAPI + Next.js + Evolution API). Vocabulário do domínio em `CONTEXT.md`; decisões em `docs/adr/`.

## Layout

- `backend/`: FastAPI, SQLAlchemy, Alembic, consumer RabbitMQ.
- `frontend/`: Next.js 16 / React 19 (tem seu próprio `frontend/AGENTS.md`).
- `docs/`: documentação versionada, ADRs e guias para agentes.

## Comandos

- Testes backend: `cd backend && rm -f test.db && env -u DATABASE_URL ./venv/bin/python -m pytest tests unit_tests --ignore=tests/e2e && rm -f test.db`
- Migrações: `cd backend && ./venv/bin/alembic upgrade head` (cadeia fixa em `docs/agents/migrations.md`).
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
