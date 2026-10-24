# Neuralilux: guia para agentes

Agente de atendimento por WhatsApp com IA (FastAPI + Next.js + Evolution API). Vocabulário do domínio em `CONTEXT.md`; decisões em `docs/adr/`.

## Layout

- `backend/`: FastAPI, SQLAlchemy, Alembic, consumer RabbitMQ. `app/{agent,api,core,llm,models,packs,realtime,schemas,services,whatsapp}`; worker em `scripts/run_worker.py`.
- `frontend/`: Next.js 16 / React 19 (tem seu próprio `frontend/AGENTS.md`).
- `docs/`: `setup.md`, `architecture.md`, `agent.md`, `packs.md`, `integrations.md`, `operations.md`, `dashboard.md`; `adr/` (decisões) e `agents/` (guias para agentes). Índice no `README.md` da raiz.
- `docker-compose.example.yml`: modelo versionado da infra local e, no perfil `app`, da aplicação em containers (`migrate`, `api`, `worker`, `frontend`), sem segredos nem senhas padrão. O `docker-compose.yml` real é local e ignorado. Imagens: `backend/Dockerfile` (API, worker e migração, mesma imagem), `frontend/Dockerfile` (Next `standalone`) e `docker/evolution/Dockerfile` (Evolution sem root); todas rodam sem root e a CI (`.github/workflows/images.yml`) constrói as três, confere `id -u` e valida o compose nos dois modos (só infra, sem `SECRET_KEY`; e `--profile app`). As bases têm digest (`@sha256`), exceto a da Evolution, cuja versão vem de `EVOLUTION_VERSION`.
- `docs/agents/evolution-data-formats.md`: formatos reais da Evolution (findChats/findMessages/findContacts/fetchAllGroups, tipos de mensagem, `@lid`, eventos do webhook e `WEBHOOK_EVENTS_*`). Leia antes de mexer no parser ou no consumer.

## Comandos

- Testes backend: `cd backend && rm -f test.db && env -u DATABASE_URL ./venv/bin/python -m pytest tests --ignore=tests/e2e -q -n auto; rm -f test.db` (paralelo com pytest-xdist; ~25 s. O bcrypt usa custo 4 só nos testes, em `tests/conftest.py`; produção segue em 12)
- Infra local: `cp docker-compose.example.yml docker-compose.yml && docker compose --env-file backend/.env up -d` (precisa de `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `RABBITMQ_PASSWORD`, `EVOLUTION_DB_PASSWORD`, `EVOLUTION_API_KEY` e `EVOLUTION_WEBHOOK_TOKEN` no `backend/.env`; o `.env.example` traz os de dev). Com a aplicação em containers: acrescente `--profile app --build` (e `SECRET_KEY`/`GATEWAY_ENCRYPTION_KEY`, que o compose não exige mas a app sim). Volumes da Evolution do compose antigo precisam do `chown` de `docs/setup.md` (seção 2).
- Migrações: `cd backend && ./venv/bin/alembic upgrade head` (cadeia fixa em `docs/agents/migrations.md`).
- Worktrees (caminhos absolutos, `npm ci` por worktree, conferir o checkout principal antes de reportar): `docs/agents/worktrees.md`.
- Seed de dev: `cd backend && SEED_DEV_SUPERUSER=1 ./venv/bin/python scripts/seed_data.py`.
- API e worker: `cd backend && ./venv/bin/uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload` e `./venv/bin/python scripts/run_worker.py`.
- Re-criptografar chaves de Gateway (da `SECRET_KEY` para a `GATEWAY_ENCRYPTION_KEY`): `cd backend && ./venv/bin/python scripts/reencrypt_gateway_secrets.py`. Passo único obrigatório ao atualizar um banco existente, antes de subir a app, com `GATEWAY_ENCRYPTION_KEY` real (o script recusa a de exemplo) e a `SECRET_KEY` antiga no `.env`; faça `pg_dump -t inference_gateways` antes; idempotente. Só ele re-criptografa: o `seed_data.py` não.
- Criar/promover superusuário (só superuser edita Gateways): `cd backend && SUPERUSER_EMAIL=... SUPERUSER_PASSWORD=... ./venv/bin/python scripts/create_superuser.py`. Em dev, `SEED_DEV_SUPERUSER=1` no `seed_data.py` promove o usuário de teste.
- Frontend: `cd frontend && npx eslint . && npx tsc --noEmit && npm test && npx next build`
- Acessibilidade do frontend: todo modal usa `components/ui/Dialog.tsx` (`<dialog>` nativo; o pai monta para abrir e desmonta em `onClose`). Botão só com ícone leva `aria-label` e `type`; toggle é `role="switch"` com `aria-checked`; todo `<label>` aponta para o controle (`htmlFor`/`id`). O lint `jsx-a11y` (regras recomendadas, todas como erro, em `frontend/eslint.config.mjs`) pega boa parte disso, mas não substitui validação com leitor de tela e revisão manual.
- CI (`.github/workflows/backend.yml` e `frontend.yml`, em todo PR para `main`, sem segredos): o frontend roda o comando acima mais `npm audit --omit=dev --audit-level=high`; o backend roda a suíte SQLite, `ruff check --select F app`, `alembic heads` com uma só head, o limite de 400 linhas e `pip-audit` (versão fixa instalada só no CI; exceções sem correção comentadas no workflow), mais os jobs `postgres` e `rabbitmq` (abaixo). Local equivalente: `cd backend && ./venv/bin/ruff check --select F app && DATABASE_URL=sqlite:///./ci.db ./venv/bin/alembic heads; rm -f ci.db; ./venv/bin/python scripts/check_max_lines.py` (`alembic heads` deve listar uma única `(head)`).
- Testes Postgres (marcador `postgres`: migrações `upgrade → downgrade → upgrade`, models x schema migrado, FTS da History Search, índice parcial do Payment Record, agregação do dashboard): `cd backend && env -u DATABASE_URL TEST_POSTGRES_URL=postgresql://<usuario>:<senha>@localhost:5434/postgres ./venv/bin/python -m pytest tests/postgres -m postgres -q`. A URL aponta para o *servidor* do compose (usuário com CREATEDB); cada execução cria bancos `nlx_pgtest_*` descartáveis e os apaga, sem tocar no banco `neuralilux`. Sem `TEST_POSTGRES_URL` esses testes são pulados e a suíte SQLite não muda. No CI é o job `postgres` do `backend.yml`.
- Testes RabbitMQ (marcador `rabbitmq`: dead-letter da fila de webhooks, overflow `drop-head`, `replay` da DLQ e `migrate` de uma fila antiga): `cd backend && env -u DATABASE_URL ENVIRONMENT=development TEST_RABBITMQ_URL=amqp://<usuario>:<senha>@localhost:5672/ ./venv/bin/python -m pytest tests/whatsapp/test_dead_letter_rabbitmq.py -m rabbitmq -q`. Cada teste usa filas `test.<id>.webhooks` próprias e as apaga; nunca toca em `webhooks.evolution`. Sem `TEST_RABBITMQ_URL` são pulados (a lógica da dead-letter também tem teste com broker simulado, `test_dead_letter.py`, na suíte normal). No CI é o job `rabbitmq` do `backend.yml`. Operação da DLQ e migração de uma fila antiga: `backend/scripts/queue_admin.py` e `docs/operations.md`.
- Instalar deps Python: `PIP_CONFIG_FILE=/dev/null ./venv/bin/pip install --index-url https://pypi.org/simple -r requirements-dev.txt` (`requirements.txt` é só runtime, o que vai para a imagem; `requirements-dev.txt` inclui ele mais pytest, lint e tipos).

## Regras

- Dependências com versão exata (`==` no Python, versão sem `^` no npm). Actions dos workflows por SHA, com a versão em comentário.
- Segredos: sem `ENVIRONMENT=development` explícito a app recusa `SECRET_KEY`, `EVOLUTION_WEBHOOK_TOKEN` e `GATEWAY_ENCRYPTION_KEY` vazios, de exemplo ou (as duas chaves) com menos de 32 caracteres, e esconde `/docs`. `GATEWAY_ENCRYPTION_KEY` só cifra as chaves dos Gateways; a `SECRET_KEY` só assina o JWT. Os testes definem `ENVIRONMENT=development` em `tests/conftest.py`; a CI não tem segredos.
- Nunca commitar `backend/.env`, `docker-compose.yml` ou `design/` (ignorados).
- Toda mudança entra por PR revisado; nunca push direto em `main`.
- Testes rodam em SQLite; o que depende de Postgres leva `@pytest.mark.postgres` (em `tests/postgres/`); e2e só com `RUN_E2E=1`.
- Warning falha a suíte (`filterwarnings = error` em `backend/pytest.ini`): corrija a causa no código. Só biblioteca de terceiros que não dá para corrigir ganha um `ignore` comentado ali.
- Código do núcleo (`backend/app/agent/`) não conhece nenhum ramo de negócio; o que é de um ramo vive num Pack (ADR 0004).

## Agent skills

### Issue tracker

Issues e PRDs ficam no GitHub Issues de `levygit837-cyber/Neuralilux`, via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Os cinco papéis canônicos com os nomes default (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` e `docs/adr/` na raiz. See `docs/agents/domain.md`.
