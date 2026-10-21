# Neuralilux Backend

API backend em Python + FastAPI para o sistema Neuralilux.

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
├── scripts/              # run_worker.py, seeds e utilitários
├── tests/                # api/, agent/, packs/, whatsapp/, realtime/, llm/, models/, core/, scripts/
├── alembic/              # Migrações de banco
├── requirements.txt
└── Dockerfile
```

## Setup Local

Requer Python 3.11 ou 3.12 e a infra do `docker-compose.yml` no ar
(`docker compose up -d postgres redis rabbitmq evolution-api`).

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # runtime + ferramentas de teste/lint; produção usa só requirements.txt

cp .env.example .env   # ajuste EVOLUTION_API_KEY, EVOLUTION_WEBHOOK_TOKEN e SECRET_KEY; o modelo é configurado como Gateway

# Banco já existente com Gateways gravados antes do HKDF: PASSO ÚNICO OBRIGATÓRIO, antes de subir a app
python scripts/reencrypt_gateway_secrets.py

# Banco novo: aplicar migrations (baseline 0001) e popular dados
alembic upgrade head
python scripts/seed_data.py   # cria um Agent por Company e liga as Instances da Company; SEED_DEV_SUPERUSER=1 promove o usuário de dev a superuser

# Primeiro superusuário (só superuser edita Gateways)
SUPERUSER_EMAIL=admin@empresa.com SUPERUSER_PASSWORD='...' python scripts/create_superuser.py

# API (entrypoint com Socket.IO) e worker
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
python scripts/run_worker.py
```

## Gateways de inferência

Todo modelo é acessado por um Gateway que fala o protocolo Anthropic Messages (`POST {base_url}/v1/messages`,
ADR 0002). Cadastre-o em **Configurações > Gateways** ou em `/api/v1/gateways`; `base_url` é a raiz, sem `/v1`
(`http://localhost:5580`). Cada Gateway tem modelos nomeados (id no Gateway, `reasoning_effort`, `max_tokens`,
`temperature`) e cada tipo de agente (`default`, `whatsapp_agent`) aponta para um modelo. Sem atribuição própria
vale `default`; sem `default` a inferência falha com `LLMNotConfiguredError`.

- `seed_data.py` cadastra o Gateway `Kiro-backend` (`claude-sonnet-5.5`, effort `low`) e o atribui a `default`.
- Cliente (`app/llm/client.py`): `effort` vai em `output_config.effort`; timeout de 60 s por padrão; retry
  (3 tentativas, backoff exponencial) em 429, 5xx e timeout. Resposta fora do formato vira `LLMProviderError`.
- Probe (`POST /gateways/models/{id}/test`, `max_tokens: 8`) e `GET /gateways/{id}/remote-models`
  (`GET {base_url}/v1/models`; 404 devolve os modelos cadastrados) usam tentativa única e timeout de 15 s.
- Criar, editar, apagar, atribuir e testar Gateways exige **superuser** (`base_url` é alvo de SSRF); leitura exige
  só login. `base_url` aceita apenas `http`/`https`, sem usuário/senha. Mudar a origem (esquema, host ou porta)
  exige informar `api_key` de novo (`""` apaga a salva).
- Primeiro superusuário: `scripts/create_superuser.py` (e-mail/senha por `SUPERUSER_EMAIL`/`SUPERUSER_PASSWORD`
  ou `--email`/`--password`; idempotente, promove usuário existente, nunca imprime a senha).
  Em dev, `SEED_DEV_SUPERUSER=1 python scripts/seed_data.py` promove o usuário `usuario@teste.com`.
- A chave de API é criptografada com Fernet derivada de `SECRET_KEY` via HKDF
  (`info=b"neuralilux-gateway-secrets"`). Trocar `SECRET_KEY` exige regravar as chaves. A app recusa subir com a
  `SECRET_KEY` de exemplo quando `ENVIRONMENT != development`.
- **Passo único ao atualizar de versões anteriores ao HKDF:** rode `python scripts/reencrypt_gateway_secrets.py`
  **antes de iniciar a app**. Converte as chaves gravadas com SHA-256 puro; é idempotente (segunda execução
  converte 0). Sem isso, essas chaves não abrem e o Gateway responde `LLMNotConfiguredError`.

## Agent

O Agent roda num loop próprio em `app/agent/` (ADR 0001), sem framework de agentes:

- `executor.handle_incoming` é chamado pelo consumer para cada Message de texto do Contact. Conversation em Handoff
  (`human_in_loop`, lido do banco) não recebe resposta.
- O contexto é o Summary mais a Recent Window (`memory.py`); as Tools vêm do núcleo (`core_tools.py`) e do Pack do
  Business Type da Company (`app/packs/`).
- `loop.run_turn` chama o modelo e executa os `tool_use` até `end_turn`, uma Tool com `ends_turn` ou `max_steps`.
- `events.py` emite `thinking` e `tool_event` na sala da Conversation; `formatting.py` converte o markdown para o WhatsApp.

## Endpoints Principais

- `GET /health` - Health check
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/instances` - Listar instâncias
- `POST /api/v1/messages/send` - Enviar mensagem
- `POST /api/v1/webhooks/evolution?token=...` - Webhook Evolution API (401 sem `?token=` igual a `EVOLUTION_WEBHOOK_TOKEN`, ADR 0006)

## Testes

```bash
# Executar todos os testes (e2e só com RUN_E2E=1)
pytest tests --ignore=tests/e2e

# Com cobertura
pytest --cov=app tests --ignore=tests/e2e

# Uma área
pytest tests/whatsapp
```

## Documentação da API

Acesse `/docs` quando o servidor estiver rodando.

## Webhook da Evolution

A Evolution chama o backend com o token na query string. Exemplo versionado em [`docker-compose.example.yml`](../docker-compose.example.yml)
(o `docker-compose.yml` real é ignorado pelo git). No serviço `evolution-api`, use:

```yaml
- WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false
- WEBHOOK_GLOBAL_URL=http://host.docker.internal:8000/api/v1/webhooks/evolution?token=${EVOLUTION_WEBHOOK_TOKEN}
```

- Exporte o mesmo `EVOLUTION_WEBHOOK_TOKEN` do `backend/.env` ao subir o compose.
- Mantenha `WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false`: o evento já vem em `payload.event`. Com `true` a Evolution anexa
  `/<evento>` ao fim da URL e o token chega como `TOKEN/messages-upsert`. O backend compara só a parte antes da primeira
  `/` (tempo constante) e usa o resto como tipo do evento quando o payload não traz `event`, mas isso é tolerância, não o caminho recomendado.
- Fora de `ENVIRONMENT=development` a app recusa subir com `EVOLUTION_WEBHOOK_TOKEN` vazio ou `change-me...`.
- O access log do uvicorn mascara `?token=`; proxies reversos na frente da API precisam fazer o mesmo.

O worker (`scripts/run_worker.py`) usa `aio-pika` num único event loop, com `RABBITMQ_PREFETCH=8` mensagens em paralelo e ordem garantida por Conversation. Uma mensagem que falha volta à fila uma vez; se falhar de novo na reentrega, é descartada e logada em `error`. Instance desconhecida é descartada: cadastre a Instance antes de conectar o número.

### Agent e resposta automática

- `scripts/seed_data.py` cria um Agent por Company e liga as Instances da Company com `agent_enabled=True`, então um seed novo já responde.
- Instances criadas por `POST /api/v1/instances` (`instances.py`) nascem com `agent_enabled=False` e sem Agent: atribua um Agent e ligue
  a resposta automática (`agent_enabled`) antes de esperar respostas. Reexecutar o seed não religa uma Instance que o operador desligou.
