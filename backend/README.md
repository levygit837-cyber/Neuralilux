# Neuralilux Backend

API FastAPI, worker RabbitMQ e Agent de atendimento por WhatsApp. A documentação do projeto vive em [`../docs/`](../docs/); este arquivo guarda só o que é específico do backend e aponta para o resto.

| Quero… | Veja |
|---|---|
| Subir tudo do zero (infra, `.env`, migrações, seed, QR code) | [setup.md](../docs/setup.md) |
| Entender o fluxo webhook → consumer → executor → loop → Tools | [architecture.md](../docs/architecture.md) |
| Loop, memória e eventos do Agent | [agent.md](../docs/agent.md) |
| Criar um Pack para outro ramo | [packs.md](../docs/packs.md) |
| Integrar um sistema de gestão | [integrations.md](../docs/integrations.md) |
| Handoff, Tickets e troubleshooting | [operations.md](../docs/operations.md) |
| Decisões de arquitetura | [adr/](../docs/adr/) |
| Cadeia de migrações Alembic | [agents/migrations.md](../docs/agents/migrations.md) |

## Estrutura

```
backend/
├── app/
│   ├── main.py           # Aplicação FastAPI (entrypoint: app.main:socket_app)
│   ├── core/             # config, database, security, crypto, logging
│   ├── api/              # deps.py (get_db, get_current_user) e router.py
│   │   └── routes/       # uma rota por assunto, sob /api/v1
│   ├── models/           # Modelos SQLAlchemy, um módulo por agregado
│   ├── schemas/          # Schemas Pydantic, agrupados como os models
│   ├── llm/              # Cliente Anthropic Messages, registry de Gateways, erros
│   ├── agent/            # Loop do Agent, Tools, executor, memória, prompts
│   ├── packs/            # Packs por Business Type (catalog_orders)
│   ├── whatsapp/         # Cliente Evolution, consumer RabbitMQ, parser de webhook, sender
│   ├── realtime/         # Socket.IO, event bus Redis, eventos de Tool
│   └── services/         # Serviços de domínio (companies, orders, menu/…)
├── scripts/              # run_worker.py, seed_data.py, create_superuser.py, reencrypt_gateway_secrets.py
├── tests/                # api/, agent/, packs/, whatsapp/, realtime/, llm/, models/, core/, scripts/
├── alembic/              # Migrações de banco
├── requirements.txt      # runtime (o que vai para a imagem)
├── requirements-dev.txt  # runtime + testes, lint e tipos
└── Dockerfile
```

## Comandos

Com o venv ativo, a partir de `backend/`:

```bash
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload   # API (docs em /docs)
python scripts/run_worker.py                                       # worker: webhooks e Agent
alembic upgrade head
SEED_DEV_SUPERUSER=1 python scripts/seed_data.py
SUPERUSER_EMAIL=admin@empresa.com SUPERUSER_PASSWORD='...' python scripts/create_superuser.py
```

Banco existente com chaves de Gateway criptografadas com a `SECRET_KEY`: defina `GATEWAY_ENCRYPTION_KEY` no `.env` e rode `python scripts/reencrypt_gateway_secrets.py` **antes** de subir a app (passo único, idempotente). Contexto em [setup.md](../docs/setup.md#banco-já-existente-chaves-de-gateway-gravadas-com-a-secret_key).

## Testes

```bash
rm -f test.db && env -u DATABASE_URL ./venv/bin/python -m pytest tests --ignore=tests/e2e -n auto; rm -f test.db
./venv/bin/python -m pytest tests/whatsapp          # uma área
./venv/bin/python -m pytest --cov=app tests --ignore=tests/e2e
```

Os testes rodam em SQLite (`tests/conftest.py` força `DATABASE_URL` para um arquivo SQLite próprio de cada processo em `$TMPDIR/neuralilux-test-<pid>.db`, removido ao fim; duas suítes em paralelo não se atrapalham e `rm -f test.db` é inofensivo); `env -u DATABASE_URL` evita tocar no banco de desenvolvimento. Os e2e só rodam com `RUN_E2E=1`.

## Gateways de inferência

Todo modelo é acessado por um Gateway que fala o protocolo Anthropic Messages ([ADR 0002](../docs/adr/0002-anthropic-messages-via-gateways.md)). Cadastro e atribuição: [setup.md](../docs/setup.md#5-gateway). Chaves criptografadas (HKDF): [setup.md](../docs/setup.md#banco-já-existente-com-gateways-gravados-antes-do-hkdf). Erros e timeouts: [operations.md](../docs/operations.md#o-agent-não-responde).

## Webhook da Evolution

`POST /api/v1/webhooks/evolution?token=...` exige `EVOLUTION_WEBHOOK_TOKEN` ([ADR 0006](../docs/adr/0006-webhook-token-auth.md)). Configuração em [setup.md](../docs/setup.md#2-infra-postgresql-redis-rabbitmq-evolution); fluxo do consumer em [architecture.md](../docs/architecture.md); diagnóstico em [operations.md](../docs/operations.md#o-webhook-não-chega-à-fila).
