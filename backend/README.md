# Neuralilux Backend

API backend em Python + FastAPI para o sistema Neuralilux.

## Estrutura

```
backend/
├── app/
│   ├── api/              # Endpoints da API
│   │   └── v1/
│   │       ├── endpoints/
│   │       └── router.py
│   ├── core/             # Configurações centrais
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── models/           # Modelos SQLAlchemy
│   ├── services/         # Lógica de negócio
│   ├── agents/           # Agentes de IA
│   └── main.py           # Aplicação FastAPI
├── tests/                # Testes
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
pip install -r requirements.txt

cp .env.example .env   # ajuste EVOLUTION_API_KEY, SECRET_KEY e a chave do LLM

# Banco novo: aplicar migrations (baseline 0001) e popular dados
alembic upgrade head
python scripts/seed_data.py

# API (entrypoint com Socket.IO) e worker
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
python scripts/run_worker.py
```

## Gateways de inferência

Qualquer API compatível com OpenAI (`POST {base_url}/chat/completions`) pode ser cadastrada em
**Configurações > Gateways** ou em `/api/v1/gateways`. Cada gateway tem modelos nomeados
(id no gateway, `reasoning_effort`, `max_tokens`, `temperature`, suporte a ferramentas) e cada tipo de agente
(`default`, `whatsapp_agent`) aponta para um modelo. Sem atribuição, valem Vertex e Gemini.

- `seed_data.py` cadastra o gateway `Kiro-backend` (`claude-sonnet-5.5`, effort `low`) e o atribui a `default`.
- A chave de API é criptografada com uma chave derivada de `SECRET_KEY`; trocar `SECRET_KEY` exige regravar as chaves.
- Se o gateway falhar antes do primeiro token, o agente cai nos provedores padrão; depois do primeiro token o erro sobe, para não duplicar texto.
- O cliente normaliza mensagens e ferramentas do formato Gemini para OpenAI, separa `reasoning_content` de `content`,
  junta `tool_calls` em streaming e aceita `<tool_call>{json}</tool_call>` emitido como texto.

## Endpoints Principais

- `GET /health` - Health check
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/instances` - Listar instâncias
- `POST /api/v1/messages/send` - Enviar mensagem
- `POST /api/v1/webhooks/evolution` - Webhook Evolution API

## Testes

```bash
# Executar todos os testes
pytest

# Com cobertura
pytest --cov=app tests/

# Teste específico
pytest tests/test_auth.py
```

## Documentação da API

Acesse `/docs` quando o servidor estiver rodando.
