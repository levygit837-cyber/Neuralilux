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

```bash
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
nano .env

# Executar migrações
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload
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
