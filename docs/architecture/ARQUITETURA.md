# Arquitetura do Sistema Neuralilux

## Visão Geral

Sistema de automação de conversas WhatsApp com IA, focado em atendimento inteligente para pequenas e médias empresas.

## Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │   Dashboard      │              │  Chat Interface  │         │
│  │   - Instâncias   │              │  - Tempo Real    │         │
│  │   - Configs      │              │  - Histórico     │         │
│  │   - Analytics    │              │  - Personalizar  │         │
│  └──────────────────┘              └──────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                            ↕ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    API Layer                                │ │
│  │  /auth  /instances  /agents  /messages  /webhooks          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            ↕                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                 Business Logic Layer                        │ │
│  │                                                             │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │ │
│  │  │   Instance   │  │    Agent     │  │   Message    │    │ │
│  │  │   Manager    │  │ Orchestrator │  │   Handler    │    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            ↕                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              AI Agent Layer (LangChain)                     │ │
│  │                                                             │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │ │
│  │  │  Agent   │  │   RAG    │  │  Memory  │  │  Tools   │  │ │
│  │  │ Builder  │  │  Engine  │  │  Store   │  │  Chain   │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                            ↕                                     │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              WhatsApp Adapter Layer                         │ │
│  │  - API Client para Evolution API                           │ │
│  │  - Webhook Handler                                          │ │
│  │  - Message Queue                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                            ↕ REST API
┌─────────────────────────────────────────────────────────────────┐
│                   Evolution API (Docker)                         │
│  - WhatsApp Web Integration (Baileys)                           │
│  - Message Handling                                             │
│  - Media Processing                                             │
└─────────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────────┐
│                      WhatsApp Servers                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  PostgreSQL  │  │    Redis     │  │  Vector DB   │          │
│  │  - Users     │  │  - Cache     │  │  - RAG       │          │
│  │  - Instances │  │  - Sessions  │  │  - Embeddings│          │
│  │  - Messages  │  │  - Queue     │  │              │          │
│  │  - Agents    │  │              │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   OpenAI     │  │   Anthropic  │  │  Local LLM   │          │
│  │     API      │  │    Claude    │  │   (Ollama)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Componentes Principais

### 1. Frontend (React/Next.js)

**Dashboard**
- Gerenciamento de instâncias WhatsApp
- Configuração de agentes
- Analytics e métricas
- Gerenciamento de usuários

**Chat Interface**
- Visualização em tempo real das conversas
- Personalização de agentes por conversa
- Histórico de mensagens
- Intervenção manual quando necessário

### 2. Backend (Python + FastAPI)

**API Layer**
- Autenticação JWT
- CRUD de instâncias, agentes, mensagens
- WebSocket para tempo real
- Webhook receiver para Evolution API

**Business Logic**
- Instance Manager: Gerencia conexões WhatsApp
- Agent Orchestrator: Coordena agentes IA
- Message Handler: Processa mensagens entrada/saída

**AI Agent Layer**
- Agent Builder: Cria agentes personalizados
- RAG Engine: Busca em documentos da empresa
- Memory Store: Contexto de conversas
- Tools Chain: Ferramentas disponíveis para agentes

**WhatsApp Adapter**
- Abstração da Evolution API
- Gerenciamento de webhooks
- Fila de mensagens
- Retry logic

### 3. Evolution API (Docker)

- Container isolado
- Gerencia protocolo WhatsApp
- Processa mídia
- Envia webhooks para nosso backend

### 4. Data Layer

**PostgreSQL**
- Usuários e autenticação
- Instâncias WhatsApp
- Histórico de mensagens
- Configurações de agentes
- Analytics

**Redis**
- Cache de sessões
- Fila de mensagens
- Rate limiting
- Temporary data

**Vector Database (Qdrant/Pinecone)**
- Embeddings de documentos
- RAG para empresas com muito conteúdo
- Busca semântica

### 5. External Services

**LLM Providers**
- OpenAI (GPT-4)
- Anthropic (Claude)
- Local (Ollama) para privacidade

## Fluxo de Mensagens

### Mensagem Recebida (Cliente → Sistema)

```
1. Cliente envia mensagem no WhatsApp
2. Evolution API recebe via Baileys
3. Evolution API envia webhook para nosso backend
4. Backend processa webhook e extrai dados
5. Message Handler identifica instância e agente
6. Agent Orchestrator carrega contexto (RAG + Memory)
7. LLM processa mensagem e gera resposta
8. Backend envia resposta via Evolution API
9. Evolution API envia para WhatsApp
10. Cliente recebe resposta
11. Frontend atualiza em tempo real (WebSocket)
```

### Mensagem Enviada (Sistema → Cliente)

```
1. Usuário envia mensagem manual pelo dashboard
2. Frontend envia via WebSocket/HTTP
3. Backend valida e processa
4. WhatsApp Adapter envia via Evolution API
5. Evolution API envia para WhatsApp
6. Confirmação retorna ao frontend
```

## Segurança

- JWT para autenticação
- Rate limiting por instância
- Validação de webhooks (assinatura)
- Criptografia de dados sensíveis
- Isolamento de instâncias por tenant
- HTTPS obrigatório

## Escalabilidade

- Backend stateless (horizontal scaling)
- Redis para sessões compartilhadas
- Fila de mensagens para processamento assíncrono
- Cache agressivo de embeddings
- Connection pooling no banco

## Monitoramento

- Logs estruturados (JSON)
- Métricas de performance
- Alertas de falhas
- Dashboard de saúde do sistema
- Tracking de custos de IA
