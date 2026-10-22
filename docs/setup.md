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
- `EVOLUTION_DB_PASSWORD` (opcional): senha do usuário `evolution` no PostgreSQL. Entra na URI do banco da Evolution, então use só letras, dígitos, `-` e `_` (`@ : / ? # %` quebram a URI). Vazio, vale o default de desenvolvimento do compose e do script de init.

As demais variáveis do `.env.example` já batem com a infra do passo 2.

## 2. Infra (PostgreSQL, Redis, RabbitMQ, Evolution)

O `docker-compose.yml` é **local e ignorado pelo git**, porque pode conter credenciais suas. O repositório traz o modelo [`docker-compose.example.yml`](../docker-compose.example.yml), sem segredos: as senhas são defaults de desenvolvimento e `EVOLUTION_API_KEY` e `EVOLUTION_WEBHOOK_TOKEN` vêm do `backend/.env`.

```bash
cp docker-compose.example.yml docker-compose.yml
docker compose --env-file backend/.env up -d
docker compose --env-file backend/.env ps    # postgres, redis e rabbitmq "healthy"; a Evolution leva alguns segundos para subir
```

O PostgreSQL cria o banco `neuralilux` e, pelo script [`scripts/init-multiple-databases.sh`](../scripts/init-multiple-databases.sh), o banco e o usuário da Evolution. O script só roda na **primeira** criação do volume `postgres_data`.

Com Colima (ou qualquer Docker em VM), o repositório precisa estar num caminho que a VM enxerga, como dentro do seu `$HOME`. Num clone em `/tmp`, o arquivo é montado como diretório vazio, o script não roda e a Evolution reinicia em loop com `P1000 Authentication failed`. Veja o [troubleshooting](operations.md#a-evolution-reinicia-em-loop).

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

O seed cria os Business Types, a Company "Empresa Teste" e a Company "Macedos" (restaurante) com cardápio, horários, fuso, pedido mínimo e uma Delivery Zone, o usuário de desenvolvimento `usuario@teste.com` (vinculado à Macedos, senha `teste123`, só para dev), um Agent por Company e o Gateway `Kiro-backend`, atribuído ao tipo `default`. É idempotente.

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

Documentação interativa da API: `http://localhost:8000/docs`. Ela só existe com `ENVIRONMENT=development`; fora disso `/docs` e `/redoc` respondem 404 (o `/openapi.json` continua disponível).

## 4. Frontend

```bash
cd frontend
cp .env.example .env.local    # aponta para a API (NEXT_PUBLIC_API_URL); o frontend só fala com o backend
npm install
npm run dev                   # http://localhost:3000
```

Entre com `usuario@teste.com` / `teste123`.

## 5. Gateway

O seed já cadastrou o `Kiro-backend` (modelo `claude-sonnet-5.5`, effort `low`) e o atribuiu a `default`. Para usar outro, entre como superuser e abra **Configurações > Gateways**, ou use `/api/v1/gateways`. `base_url` é a raiz, sem `/v1` (`http://localhost:5580`). Sem atribuição para `whatsapp_agent` vale a de `default`; sem nenhuma, o Turn falha com `LLMNotConfiguredError`.

Para testar a conexão, use **Testar** no modelo ou `POST /api/v1/gateways/models/{id}/test`.

## 6. Conectar o WhatsApp (QR code)

A ordem importa: a Instance precisa existir no banco (com Company) **antes** de ler o QR code. O evento `connection.update` de uma Instance sem linha no banco é descartado (`Connection update for unknown instance discarded`), e o status nunca chega a `connected`.

O fluxo é: login, `POST /api/v1/instances/{nome}`, QR code. A Company vem do usuário que cria a Instance, então entre com um usuário que tenha Company (o `usuario@teste.com` do seed tem).

1. Faça login e crie a Instance. No dashboard, vá em **Instâncias**; por REST:
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
     -d 'username=usuario@teste.com' -d 'password=teste123' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
   curl -s -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/instances/minha-instancia
   ```
   A rota cria a Instance na Evolution, **depois** grava a linha local com o usuário como dono e a Company dele, e devolve o QR code em `qr_code`.
2. No celular: WhatsApp > Aparelhos conectados > Conectar um aparelho, e leia o QR code. Se ele não veio na criação, `POST /api/v1/instances/{nome}/connect` devolve outro; o QR também chega em `qr_code_update` pelo Socket.IO.
3. O estado passa a `connected` pelo evento `connection.update` do webhook.

### Ligar a Instance à Company e ao Agent

A Instance só responde quando tem Company, Agent e a resposta automática ligada. Não há passo manual no banco: o `POST /instances/{nome}` grava `company_id` (o do usuário) e, se a Company já tem um Agent ativo, liga esse Agent à Instance com `agent_enabled=true`.

Se a Company ainda não tinha Agent na hora da criação, o worker loga `No active Agent for this Instance or its Company`. Rode o seed, que cria um Agent por Company e liga as Instances da Company que ainda não têm Agent (idempotente):

```bash
cd backend && python scripts/seed_data.py
```

Reexecutar o seed não religa uma Instance que o administrador desligou. O Agent da Instance também pode ser trocado por `PATCH /api/v1/instances/{nome}/agent-binding` e a resposta automática ligada ou desligada por `PATCH /api/v1/instances/{nome}/agent-status`. Essas duas rotas e `GET .../agent-status` só funcionam em Instance que já existe (404 se não houver linha) e que é sua (403 se é de outro dono).

### Quem acessa uma Instance

- Toda rota de `/api/v1/instances` exige login. O dono (`owner_id`) e o superusuário acessam; outro usuário recebe 403.
- `GET /instances/` lista só as Instances do usuário (superusuário: todas) e nunca devolve o token da Evolution.
- Só `POST /instances/{nome}` cria a linha local. Se o nome já existe na Evolution, só um superusuário o importa; os demais recebem 409.
- Uma Instance sem dono (linha antiga, `owner_id` nulo) só é acessada por superusuário. Para assumi-la, um superusuário chama `POST /instances/{nome}`: ele vira o dono e a Instance ganha a Company dele e o Agent da Company.

## 7. Conferir de ponta a ponta

1. Mande "oi, qual o horário?" de outro número para o WhatsApp conectado.
2. No log do worker devem aparecer `Message saved to database`, `Turn finished` e `Agent response sent`. Com a Instance ainda não conectada ao WhatsApp, o `Turn finished` aparece (o Agent responde de fato pelo Gateway), mas o envio falha com `Evolution API request error`; conecte o QR code antes de esperar a resposta no celular.
3. O dashboard mostra a Message, o indicador de `thinking_event` e a resposta.

Se algo não responde, veja o [troubleshooting](operations.md#troubleshooting).

## Testes

```bash
cd backend
rm -f test.db && env -u DATABASE_URL ./venv/bin/python -m pytest tests --ignore=tests/e2e; rm -f test.db
cd ../frontend && npx eslint . && npx tsc --noEmit && npx next build
```

Os testes do backend rodam em SQLite; `env -u DATABASE_URL` impede que a suíte use o banco de desenvolvimento. Os e2e só rodam com `RUN_E2E=1`.
