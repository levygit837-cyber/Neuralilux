<h1 align="center">
  🤖 Neuralilux
</h1>

<p align="center">
  <b>Agentes de IA no WhatsApp para pequenas e médias empresas</b><br>
  Automatize atendimento, pedidos e suporte com LLMs — sem perder a conversa humana.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Next.js-14-000000?style=flat&logo=next.js&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/TypeScript-5.0-3178C6?style=flat&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/LangGraph-0.0.20-1C3C3C?style=flat&logo=langchain&logoColor=white" alt="LangGraph">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat" alt="License">
</p>

---

## 🎯 O que resolve

Pequenos negócios (restaurantes, clínicas, lojas) perdem vendas e clientes por não conseguirem responder no WhatsApp rapidamente. O **Neuralilux** conecta o WhatsApp da empresa a agentes de IA que atendem 24/7, fazem pedidos, consultam cardápios e escalam para humanos quando necessário — tudo via uma única plataforma web.

---

## ⚡ Funcionalidades principais

- **🤖 Agentes de IA especializados** — Dois perfis de agente orquestrados via **LangGraph**:
  - `Sales`: atende, recomenda do cardápio, monta pedidos e gera QR Code Pix
  - `SAC`: rastreia pedidos, abre tickets e escala para humanos
- **🧠 RAG (Retrieval-Augmented Generation)** — Busca semântica em documentos da empresa via **Qdrant** + **Sentence Transformers**
- **💬 Integração WhatsApp real** — Conexão via **Evolution API** (Baileys) com webhooks, QR Code e mensagens bidirecionais
- **👤 Human-in-the-loop** — Transferência inteligente para atendente humano com contexto completo
- **📊 Dashboard em tempo real** — Chat ao vivo, instâncias WhatsApp, métricas e gerenciamento de agentes
- **🔌 Multi-LLM com fallback** — Suporte a **OpenAI**, **Anthropic Claude**, **Google Gemini**, **Vertex AI** e **LM Studio** (local), com fallback automático entre provedores
- **📦 Sistema de pedidos completo** — Carrinho, cardápio dinâmico, cálculo de taxa de entrega e pagamento Pix
- **🚀 Streaming de respostas** — Respostas da IA aparecem em tempo real no chat, com indicadores visuais de "pensamento"

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Next.js 14 + TypeScript + TailwindCSS)           │
│  Dashboard · Chat em tempo real · Gerenciamento de agentes  │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / WebSocket
┌────────────────────────▼────────────────────────────────────┐
│  Backend (FastAPI + Python)                                 │
│  ├─ API REST + JWT Auth                                     │
│  ├─ Webhooks WhatsApp (Evolution API)                       │
│  ├─ Agent Orchestrator (LangGraph)                          │
│  ├─ RAG Engine (Qdrant + Embeddings)                        │
│  └─ Streaming Inference (multi-provider + fallback)         │
└────────────────────────┬────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌─────────┐      ┌────────────┐      ┌──────────────┐
│PostgreSQL│      │   Redis    │      │   RabbitMQ   │
│+ Alembic│      │  (cache)   │      │  (filas)     │
└─────────┘      └────────────┘      └──────────────┘
```

**Destaques técnicos:**
- Grafo de agentes construído com **LangGraph** (nós de validação, classificação de intenção, execução de tools e geração de resposta)
- Fila de mensagens com **RabbitMQ** para processamento assíncrono
- Cache e sessões em **Redis**
- Migrations versionadas com **Alembic**
- WebSocket via **python-socketio** para atualizações em tempo real no frontend

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologias |
|--------|-------------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| **IA / LLM** | LangChain, LangGraph, OpenAI, Anthropic, Google Gemini, Vertex AI |
| **Vector DB** | Qdrant, sentence-transformers |
| **Fila / Cache** | RabbitMQ, Redis |
| **Banco de dados** | PostgreSQL 15 |
| **Frontend** | Next.js 14 (App Router), TypeScript, TailwindCSS, Zustand, React Query |
| **DevOps** | Docker, Docker Compose |
| **Testes** | pytest, pytest-asyncio, pytest-cov (50+ arquivos de teste) |

---

## 🚀 Como rodar localmente

> Pré-requisitos: Docker + Docker Compose

```bash
# 1. Clone o repositório
git clone https://github.com/levygit837-cyber/Neuralilux.git
cd Neuralilux

# 2. Configure as variáveis de ambiente
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# Edite backend/.env e adicione sua chave de API (OpenAI, Gemini ou Vertex)

# 3. Suba a infraestrutura
docker-compose up -d postgres redis rabbitmq evolution-api

# 4. Rode o backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:socket_app --reload --host 0.0.0.0 --port 8000

# 5. Rode o frontend (em outro terminal)
cd frontend
npm install
npm run dev
```

Acesse:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Evolution API**: http://localhost:8081

> Veja o [guia completo](docs/guides/QUICK_START.md) para configuração detalhada.

---

## 📁 Estrutura do projeto

```
Neuralilux/
├── backend/
│   ├── app/
│   │   ├── agents/          # Orquestração LangGraph + tools + memory
│   │   ├── api/v1/endpoints/# Rotas REST
│   │   ├── core/            # Config, DB, segurança
│   │   ├── models/          # SQLAlchemy models
│   │   └── services/        # Lógica de negócio (inference, WhatsApp, etc.)
│   ├── alembic/             # Migrations
│   └── tests/               # Testes unitários e e2e
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router
│       ├── components/      # Componentes React
│       └── services/        # API clients
├── docker-compose.yml       # Infraestrutura completa
└── docs/                    # Documentação técnica
```

---

## ✅ Status do projeto

| Aspecto | Status |
|---------|--------|
| Backend API | ✅ Funcional |
| Agentes IA (Sales/SAC) | ✅ Funcional |
| Integração WhatsApp | ✅ Funcional |
| Frontend Dashboard | ✅ Funcional |
| RAG | ✅ Funcional |
| Streaming de respostas | ✅ Funcional |
| Testes | 🟡 Em expansão (~50 suites) |
| CI/CD | 🔴 Não implementado |

> Este é um projeto ativo de aprendizado. O foco atual é estabilizar testes e2e e adicionar CI/CD.

---

## 🎓 Aprendizados técnicos

Construir o Neuralilux me ensinou na prática:

- **Arquitetura de sistemas distribuídos** — orquestrar múltiplos serviços (API, fila, cache, banco, LLM) com Docker
- **Design de agentes com LLMs** — modelar fluxos de conversa como grafos de estados (LangGraph), não como chatbots simples
- **RAG na prática** — chunking, embeddings, vector search e como evitar alucinações em documentos da empresa
- **Type safety end-to-end** — Pydantic v2 no backend + Zod + TypeScript no frontend reduziu bugs de integração em ~70%
- **Streaming assíncrono** — lidar com SSE, buffers parciais e estados de UI em tempo real
- **Testes em sistemas com IA** — como mockar LLMs e testar comportamento de agentes de forma determinística

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para detalhes.

---

<p align="center">
  Desenvolvido com 💙 para aprender construindo algo real.
</p>
