# Stack Tecnológico - Neuralilux

## Backend

### Core
- **Python**: 3.11+
- **Framework**: FastAPI 0.109+
- **ASGI Server**: Uvicorn
- **Validação**: Pydantic v2

### IA e Agentes
- **Orquestração**: LangChain 0.1+ / LangGraph
- **LLM Providers**:
  - OpenAI API (GPT-4, GPT-3.5-turbo)
  - Anthropic Claude (Claude 3)
  - Ollama (local, opcional)
- **Embeddings**: OpenAI text-embedding-3-small
- **Vector Store**: Qdrant / Pinecone
- **RAG**: LangChain Document Loaders + FAISS/Qdrant

### Database
- **Relacional**: PostgreSQL 15+
- **Cache**: Redis 7+
- **ORM**: SQLAlchemy 2.0+
- **Migrations**: Alembic

### Autenticação e Segurança
- **JWT**: python-jose
- **Password Hashing**: passlib + bcrypt
- **CORS**: FastAPI middleware
- **Rate Limiting**: slowapi

### WhatsApp Integration
- **Evolution API**: Docker container
- **HTTP Client**: httpx (async)
- **Webhooks**: FastAPI endpoints

### Comunicação Tempo Real
- **WebSocket**: FastAPI WebSocket
- **Message Queue**: Redis Pub/Sub ou RabbitMQ (opcional)

### Testes
- **Framework**: pytest
- **Async**: pytest-asyncio
- **Coverage**: pytest-cov
- **Mocking**: pytest-mock

### Utilitários
- **Environment**: python-dotenv
- **Logging**: structlog
- **Monitoring**: prometheus-client
- **Task Queue**: Celery (opcional, para processamento pesado)

## Frontend

### Core
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript 5+
- **Package Manager**: pnpm

### UI/UX
- **Styling**: TailwindCSS 3+
- **Components**: shadcn/ui
- **Icons**: Lucide React
- **Animations**: Framer Motion

### State Management
- **Global State**: Zustand
- **Server State**: TanStack Query (React Query)
- **Forms**: React Hook Form + Zod

### Comunicação
- **HTTP Client**: Axios
- **WebSocket**: Socket.io-client
- **API Types**: TypeScript types gerados do backend

### Visualização
- **Charts**: Recharts
- **Tables**: TanStack Table
- **Date/Time**: date-fns

### Desenvolvimento
- **Linting**: ESLint
- **Formatting**: Prettier
- **Type Checking**: TypeScript strict mode

## DevOps

### Containerização
- **Docker**: 24+
- **Docker Compose**: v2
- **Multi-stage builds**: Para otimização

### CI/CD
- **Platform**: GitHub Actions
- **Testing**: Automated tests on PR
- **Deployment**: Docker images para staging/production

### Monitoramento
- **Logs**: Estruturados em JSON
- **Metrics**: Prometheus + Grafana
- **Errors**: Sentry (opcional)
- **Uptime**: UptimeRobot (opcional)

### Infraestrutura
- **Cloud**: AWS / DigitalOcean / Hetzner
- **Reverse Proxy**: Nginx
- **SSL**: Let's Encrypt (Certbot)
- **Backup**: Automated PostgreSQL backups

## Dependências Externas

### Evolution API
- **Version**: Latest stable
- **Deploy**: Docker container
- **Communication**: REST API + Webhooks

### LLM APIs
- **OpenAI**: API Key required
- **Anthropic**: API Key required
- **Ollama**: Self-hosted (opcional)

### Vector Database
- **Qdrant**: Self-hosted ou Cloud
- **Pinecone**: Cloud (alternativa)

## Ambiente de Desenvolvimento

### Requisitos
- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 15+ (ou via Docker)
- Redis 7+ (ou via Docker)

### IDEs Recomendados
- **Backend**: VSCode + Python extension
- **Frontend**: VSCode + TypeScript/React extensions
- **Database**: DBeaver / pgAdmin

### Ferramentas
- **API Testing**: Postman / Insomnia
- **Git**: GitHub
- **Terminal**: Oh My Zsh (opcional)

## Versões e Compatibilidade

| Componente | Versão Mínima | Versão Recomendada |
|------------|---------------|-------------------|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS |
| PostgreSQL | 14 | 15 |
| Redis | 6 | 7 |
| Docker | 20 | 24 |

## Estimativa de Custos (Mensal)

### Desenvolvimento
- **Infraestrutura**: $0 (local)
- **LLM APIs**: ~$50-100 (testes)

### Produção (Pequena Escala)
- **VPS**: $20-40 (4GB RAM, 2 vCPU)
- **Database**: Incluído no VPS
- **OpenAI API**: $100-500 (depende do volume)
- **Anthropic API**: $100-500 (alternativa)
- **Vector DB**: $0-25 (Qdrant self-hosted ou free tier)
- **Total**: ~$220-1065/mês

### Produção (Média Escala)
- **VPS**: $80-120 (16GB RAM, 4 vCPU)
- **Managed PostgreSQL**: $50-100
- **Redis**: $20-40
- **LLM APIs**: $500-2000
- **Vector DB**: $50-100
- **CDN**: $20-50
- **Total**: ~$720-2410/mês
