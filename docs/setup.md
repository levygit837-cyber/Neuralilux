# Setup local

Do zero até um Agent respondendo no WhatsApp, em desenvolvimento. Os termos seguem o [glossário](../CONTEXT.md). A visão geral dos processos está em [architecture.md](architecture.md).

## Pré-requisitos

- Docker com Compose v2.
- Python 3.11 ou 3.12.
- Node 20.9+ (exigência do Next 16).
- Um Gateway que fale o protocolo Anthropic Messages ([ADR 0002](adr/0002-anthropic-messages-via-gateways.md)). O seed cadastra o `Kiro-backend` apontando para `KIRO_GATEWAY_URL` (default `http://localhost:5580`).
- Um celular com WhatsApp para ler o QR code.

Portas usadas no host: PostgreSQL 5434, Redis 6380, RabbitMQ 5672 (painel 15672), Evolution 8081, API 8000, frontend 3000.

## 1. Variáveis de ambiente

```bash
cp backend/.env.example backend/.env
```

Edite `backend/.env`:

- `EVOLUTION_API_KEY`: qualquer valor forte. A Evolution usa o mesmo valor como `AUTHENTICATION_API_KEY`.
- `EVOLUTION_WEBHOOK_TOKEN`: token do webhook ([ADR 0006](adr/0006-webhook-token-auth.md)). Gere um com:
  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- `SECRET_KEY`: chave do JWT e da criptografia das chaves de Gateway. Fora de `ENVIRONMENT=development` a app recusa subir com o valor de exemplo.
- `KIRO_GATEWAY_URL` (e `KIRO_GATEWAY_API_KEY`, opcional): onde o seed aponta o Gateway inicial.

As demais variáveis do `.env.example` já batem com a infra do passo 2.

## 2. Infra (PostgreSQL, Redis, RabbitMQ, Evolution)

O `docker-compose.yml` é **local e ignorado pelo git**, porque pode conter credenciais suas. O repositório traz o modelo [`docker-compose.example.yml`](../docker-compose.example.yml), sem segredos: as senhas são defaults de desenvolvimento e `EVOLUTION_API_KEY` e `EVOLUTION_WEBHOOK_TOKEN` vêm do `backend/.env`.

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose --env-file backend/.env up -d
docker compose ps    # todos "healthy" (a Evolution pode levar alguns segundos)
```

O PostgreSQL cria o banco `neuralilux` e, pelo script [`scripts/init-multiple-databases.sh`](../scripts/init-multiple-databases.sh), o banco e o usuário da Evolution.

Quem já tem um `docker-compose.yml` próprio só precisa garantir, no serviço `evolution-api`:

```yaml
- WEBHOOK_GLOBAL_ENABLED=true
- WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false
- WEBHOOK_GLOBAL_URL=http://host.docker.internal:8000/api/v1/webhooks/evolution?token=${EVOLUTION_WEBHOOK_TOKEN}
```

`BY_EVENTS=false` é o caminho recomendado: o evento já vem em `payload.event`. Com `true` a Evolution anexa `/<evento>` ao fim da URL e o token chega como `TOKEN/messages-upsert`; o backend tolera isso, mas é só tolerância. Em Linux, o `extra_hosts: host.docker.internal:host-gateway` do compose é o que deixa o container alcançar a API no host.

## 3. Backend

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # runtime + testes/lint; a imagem de produção usa só requirements.txt
```

### Migrações

```bash
alembic upgrade head
alembic heads    # deve listar uma única head
```

A cadeia de migrações está fixa em [agents/migrations.md](agents/migrations.md).

### Banco já existente com Gateways gravados antes do HKDF

Passo único e obrigatório, antes de subir a app. É idempotente: a segunda execução converte 0 chaves. Em banco novo não há o que converter.

```bash
python scripts/reencrypt_gateway_secrets.py
```

### Seed

```bash
SEED_DEV_SUPERUSER=1 python scripts/seed_data.py
```

O seed cria os Business Types, a Company de exemplo "Macedos" (restaurante) com cardápio, horários, fuso, pedido mínimo e uma Delivery Zone, o usuário de desenvolvimento `usuario@teste.com` (senha `teste123`, só para dev), um Agent por Company e o Gateway `Kiro-backend`, atribuído ao tipo `default`. É idempotente.

`SEED_DEV_SUPERUSER=1` promove o usuário de dev a superuser, requisito para criar e editar Gateways. Sem a variável, ele fica como usuário comum. Para um usuário real:

```bash
SUPERUSER_EMAIL=admin@empresa.com SUPERUSER_PASSWORD='...' python scripts/create_superuser.py
```

O script é idempotente, promove um usuário existente e nunca imprime a senha.

### Subir API e worker

Cada um num terminal, com o venv ativo:

```bash
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
python scripts/run_worker.py
```

`--host 0.0.0.0` é necessário para o container da Evolution alcançar o webhook; a API não deve ficar exposta fora da sua máquina sem uma camada de rede na frente. Confira:

```bash
curl -s http://localhost:8000/health
```

Documentação interativa da API: `http://localhost:8000/docs`.

## 4. Frontend

```bash
cd frontend
cp .env.example .env.local    # preencha NEXT_PUBLIC_EVOLUTION_API_KEY com o EVOLUTION_API_KEY do backend
npm install
npm run dev                   # http://localhost:3000
```

Entre com `usuario@teste.com` / `teste123`.

## 5. Gateway

O seed já cadastrou o `Kiro-backend` (modelo `claude-sonnet-5.5`, effort `low`) e o atribuiu a `default`. Para usar outro, entre como superuser e abra **Configurações > Gateways**, ou use `/api/v1/gateways`. `base_url` é a raiz, sem `/v1` (`http://localhost:5580`). Sem atribuição para `whatsapp_agent` vale a de `default`; sem nenhuma, o Turn falha com `LLMNotConfiguredError`.

Para testar a conexão, use **Testar** no modelo ou `POST /api/v1/gateways/models/{id}/test`.

## 6. Conectar o WhatsApp (QR code)

1. No dashboard, vá em **Instâncias** e crie uma Instance. O frontend chama a Evolution e a API; por REST, o equivalente é `POST /api/v1/instances/{nome}` (autenticado), que cria a Instance na Evolution e devolve o QR code em `qr_code`.
2. No celular: WhatsApp > Aparelhos conectados > Conectar um aparelho, e leia o QR code. O QR vem em `qr_code_update` pelo Socket.IO e em `GET /api/v1/whatsapp/qr?instance_id=...`.
3. O estado passa a `connected` pelo evento `connection.update` do webhook.

### Ligar a Instance à Company e ao Agent

A Instance só responde quando tem Company, Agent e a resposta automática ligada. Hoje **nenhuma rota da API grava `Instance.company_id`**; sem ele o worker loga `Instance has no Company, Agent cannot run` e não responde. Faça uma vez por Instance:

```bash
# 1. garante a linha da Instance no banco (cria se não existir; precisa do token do login)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d 'username=usuario@teste.com' -d 'password=teste123' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/instances/minha-instancia/agent-status

# 2. liga a Instance à Company
docker compose exec postgres psql -U neuralilux -d neuralilux -c \
  "UPDATE instances SET company_id = (SELECT id FROM companies WHERE name = 'Macedos') WHERE name = 'minha-instancia';"

# 3. o seed liga o Agent da Company à Instance e ativa a resposta automática (idempotente)
cd backend && python scripts/seed_data.py
```

Reexecutar o seed não religa uma Instance que o operador desligou. O Agent da Instance também pode ser trocado por `PATCH /api/v1/instances/{nome}/agent-binding` e a resposta automática ligada ou desligada por `PATCH /api/v1/instances/{nome}/agent-status`.

## 7. Conferir de ponta a ponta

1. Mande "oi, qual o horário?" de outro número para o WhatsApp conectado.
2. No log do worker devem aparecer `Message saved to database`, `Turn finished` e `Agent response sent`.
3. O dashboard mostra a Message, o indicador de `thinking_event` e a resposta.

Se algo não responde, veja o [troubleshooting](operations.md#troubleshooting).

## Testes

```bash
cd backend
rm -f test.db && env -u DATABASE_URL ./venv/bin/python -m pytest tests --ignore=tests/e2e; rm -f test.db
cd ../frontend && npx eslint . && npx tsc --noEmit && npx next build
```

Os testes do backend rodam em SQLite; `env -u DATABASE_URL` impede que a suíte use o banco de desenvolvimento. Os e2e só rodam com `RUN_E2E=1`.
