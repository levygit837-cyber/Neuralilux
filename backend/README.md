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
(`docker compose up -d postgres redis rabbitmq qdrant evolution-api`).

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
