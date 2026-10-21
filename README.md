<div align="center">

# Neuralilux

**Protótipo técnico de atendimento assistido por IA para operações no WhatsApp.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

## Navegação rápida

[Problema](#o-problema) · [Implementação](#o-que-está-implementado) · [Arquitetura](#arquitetura) · [Execução](#rodar-localmente) · [Limites](#limites-atuais)

## O problema

Equipes que atendem pelo WhatsApp precisam acompanhar múltiplas instâncias, manter respostas
consistentes e conectar a conversa a dados como cardápio, pedidos, horários e entrega. O Neuralilux
explora essa operação em um dashboard único, com agentes especializados e intervenção humana.

O projeto é um protótipo técnico legado, não uma plataforma validada para produção.

## O que está implementado

- autenticação, empresas, usuários e múltiplas instâncias da Evolution API;
- conexão de instâncias por QR code e associação entre instância e agente;
- persistência de conversas e mensagens, Socket.IO e polling de contingência;
- roteamento entre agentes de vendas e atendimento;
- ferramentas ligadas ao fluxo principal para cardápio, pedido, horário e entrega;
- configuração de provedores de inferência, fallback e eventos de streaming;
- dashboard Next.js para instâncias, conversas, agente, estoque e configurações.

Há implementações isoladas de ticket e pagamento, mas elas não fecham hoje uma jornada completa pelo
dispatcher principal. Alguns cartões de configuração da interface também permanecem demonstrativos.

## Arquitetura

```text
WhatsApp / Evolution API
          │
          ▼
FastAPI ── webhooks ── roteador Sales/SAC ── tools operacionais
   │                         │
   ├── PostgreSQL            └── provedores de inferência + fallback
   ├── Redis / RabbitMQ
   │
   └── Socket.IO / REST ── dashboard Next.js
```

```text
backend/app/
├── agents/          # grafo, prompts, memória, outputs e tools
├── api/v1/          # autenticação, instâncias, conversas e configuração
└── services/        # Evolution API, inferência, catálogo e tempo real

frontend/src/
├── app/             # rotas do dashboard
├── components/      # chat, agente, métricas e configurações
├── services/        # clientes HTTP e Socket.IO
└── stores/          # estado de autenticação, chat e instâncias
```

## Rodar localmente

Pré-requisitos: Docker, Python 3.11 ou 3.12, Node 20.9+ (exigência do Next 16) e um Gateway que fale o protocolo Anthropic Messages (cadastrado depois em **Configurações > Gateways**).

```bash
# 1. Infra: PostgreSQL, Redis, RabbitMQ e Evolution API
docker compose up -d postgres redis rabbitmq evolution-api

# 2. Backend
cd backend
cp .env.example .env        # ajuste EVOLUTION_API_KEY, EVOLUTION_WEBHOOK_TOKEN e SECRET_KEY
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt   # dev: runtime + testes/lint; produção usa requirements.txt
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
python scripts/run_worker.py   # outro terminal: consome webhooks e mensagens

# 3. Frontend
cd frontend
cp .env.example .env.local
npm install && npm run dev
```

Em banco novo, rode `alembic upgrade head` e `python scripts/seed_data.py` antes de subir a API. O passo a passo
completo, incluindo a conexão do WhatsApp por QR code, está em [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

## Limites atuais

- o `docker-compose.yml` mantém defaults de desenvolvimento (chaves e senhas em texto puro);
- endpoints de tickets ainda exigem reforço de isolamento e autorização por empresa;
- as suítes não foram reproduzidas em uma instalação limpa desta versão pública;
- dependências frontend e defaults de desenvolvimento precisam de revisão antes de qualquer deploy;
- a navegação móvel e a acessibilidade ainda não passaram por validação completa;
- nenhuma métrica de clientes, disponibilidade ou uso comercial é comprovada pelo repositório.

## Documentação

- [Backend](backend/README.md)
- [Frontend](frontend/README.md)

Documentos antigos que afirmam conclusão total ou prontidão para produção devem ser tratados como
registro histórico, não como estado atual.

## Desenvolvimento

Projeto conduzido com desenvolvimento assistido por agentes de IA. O trabalho humano incluiu
definição do produto, decomposição das jornadas, direção da interface, supervisão das implementações
e revisão dos fluxos.

## Licença

[MIT](LICENSE). Dados, marcas, conversas e credenciais reais não fazem parte do repositório.
