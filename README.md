<div align="center">

# Neuralilux

**Agente de atendimento por WhatsApp com IA, configurável para o ramo de cada empresa.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

## O que é

Uma Company conecta o número de WhatsApp dela (uma Instance, via Evolution API). O Agent atende os Contacts com as Tools do Pack do seu ramo, consulta a memória da Conversation e passa para um Attendant quando precisa (Handoff). Um dashboard Next.js acompanha Instances, Conversations e o que o Agent está fazendo em tempo real.

Hoje existe um Pack, "catálogo & pedidos" (restaurantes): cardápio, pedido e Pix. Novos ramos entram como outro Pack, sem mexer no núcleo ([como criar um Pack](docs/packs.md)). O vocabulário do projeto está no [glossário](CONTEXT.md).

## Para quem

- **Donos de negócio e administradores** que atendem pelo WhatsApp e querem automatizar o atendimento com passagem para um humano.
- **Desenvolvedores** que querem rodar, estender com Packs ou integrar o sistema de gestão de uma Company.

É um projeto em evolução, sem garantias de produção: veja [Limites atuais](#limites-atuais).

## Quickstart

Pré-requisitos: Docker (Compose v2), Python 3.11 ou 3.12, Node 20.9+ e um Gateway que fale o protocolo Anthropic Messages ([ADR 0002](docs/adr/0002-anthropic-messages-via-gateways.md)).

```bash
# 1. Variáveis do backend (defina EVOLUTION_API_KEY, EVOLUTION_WEBHOOK_TOKEN e SECRET_KEY)
cp backend/.env.example backend/.env

# 2. Infra: PostgreSQL, Redis, RabbitMQ e Evolution API
cp docker-compose.example.yml docker-compose.yml
docker compose --env-file backend/.env up -d

# 3. Backend: dependências, banco e dados de exemplo
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
SEED_DEV_SUPERUSER=1 python scripts/seed_data.py
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload   # API
python scripts/run_worker.py                                       # worker, outro terminal

# 4. Frontend (outro terminal, na raiz do repositório)
cd frontend && cp .env.example .env.local && npm install && npm run dev
```

O `docker-compose.yml` é **local e ignorado pelo git**: ele pode ter credenciais suas. O repositório versiona o [`docker-compose.example.yml`](docker-compose.example.yml), sem segredos; é dele que o passo 2 parte. Entre em `http://localhost:3000` com `usuario@teste.com` / `teste123` (usuário de dev criado pelo seed).

Conectar o WhatsApp por QR code, ligar a Instance à Company e conferir a primeira resposta estão no [guia de setup](docs/setup.md).

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/setup.md](docs/setup.md) | Infra local, `.env`, migrações, seed, Gateway, QR code e primeira resposta. |
| [docs/architecture.md](docs/architecture.md) | Fluxo webhook → consumer → executor → loop → Tools → Evolution. |
| [docs/agent.md](docs/agent.md) | Loop, Tools, memória (Recent Window, Summary, History Search) e eventos. |
| [docs/packs.md](docs/packs.md) | Criar um Pack para farmácia, loja ou academia: contrato e exemplo. |
| [docs/integrations.md](docs/integrations.md) | Integrar um sistema de gestão por API REST e por Tools de Pack. |
| [docs/operations.md](docs/operations.md) | Handoff, Tickets e troubleshooting. |
| [CONTEXT.md](CONTEXT.md) | Glossário do domínio. |
| [docs/adr/](docs/adr/) | Decisões de arquitetura. |
| [backend/README.md](backend/README.md) · [frontend/README.md](frontend/README.md) | Notas de cada parte. |
| [AGENTS.md](AGENTS.md) | Guia para agentes de código: layout, comandos e regras. |

## Limites atuais

- Os defaults de desenvolvimento (senhas do compose, `usuario@teste.com`) não servem para produção; a app recusa `SECRET_KEY` e `EVOLUTION_WEBHOOK_TOKEN` de exemplo fora de `ENVIRONMENT=development`.
- Só existe o Pack de catálogo & pedidos.
- A navegação móvel e a acessibilidade do dashboard não passaram por validação completa.
- Nenhuma métrica de clientes, disponibilidade ou uso comercial é comprovada pelo repositório.

## Desenvolvimento

Projeto conduzido com desenvolvimento assistido por agentes de IA. O trabalho humano incluiu definição do produto, decomposição das jornadas, direção da interface, supervisão das implementações e revisão dos fluxos. Toda mudança entra por PR revisado.

## Licença

[MIT](LICENSE). Dados, marcas, conversas e credenciais reais não fazem parte do repositório.
