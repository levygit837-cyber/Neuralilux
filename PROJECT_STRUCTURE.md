# Estrutura do Projeto Neuralilux

## Visão Geral

```
Neuralilux/
├── backend/                    # API Python + FastAPI
│   ├── alembic/               # Migrações de banco de dados
│   │   ├── versions/          # Arquivos de migração
│   │   ├── env.py            # Configuração Alembic
│   │   └── script.py.mako    # Template de migração
│   ├── app/
│   │   ├── api/              # Endpoints da API
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── auth.py        # Autenticação
│   │   │       │   ├── instances.py   # Instâncias WhatsApp
│   │   │       │   ├── agents.py      # Agentes de IA
│   │   │       │   ├── messages.py    # Mensagens
│   │   │       │   └── webhooks.py    # Webhooks
│   │   │       └── router.py          # Router principal
│   │   ├── core/             # Configurações centrais
│   │   │   ├── config.py     # Configurações
│   │   │   └── database.py   # Conexão com banco
│   │   ├── models/           # Modelos SQLAlchemy
│   │   │   └── models.py     # User, Instance, Agent, Message
│   │   ├── services/         # Lógica de negócio
│   │   ├── agents/           # Agentes de IA (LangChain)
│   │   └── main.py           # Aplicação FastAPI
│   ├── tests/                # Testes
│   │   ├── conftest.py       # Fixtures pytest
│   │   └── test_main.py      # Testes básicos
│   ├── .env.example          # Exemplo de variáveis de ambiente
│   ├── .gitignore
│   ├── alembic.ini           # Configuração Alembic
│   ├── Dockerfile            # Container backend
│   ├── README.md
│   └── requirements.txt      # Dependências Python
│
├── frontend/                  # Dashboard Next.js
│   ├── src/
│   │   ├── app/              # App Router (Next.js 14)
│   │   │   ├── layout.tsx    # Layout principal
│   │   │   ├── page.tsx      # Página inicial
│   │   │   └── globals.css   # Estilos globais
│   │   ├── components/       # Componentes React
│   │   ├── services/         # API clients
│   │   └── styles/           # Estilos
│   ├── public/               # Assets estáticos
│   ├── .env.example
│   ├── .gitignore
│   ├── Dockerfile
│   ├── next.config.js
│   ├── package.json
│   ├── README.md
│   ├── tailwind.config.js
│   └── tsconfig.json
│
├── docs/                      # Documentação
│   ├── architecture/
│   │   ├── ARQUITETURA.md           # Arquitetura do sistema
│   │   ├── DECISAO_EVOLUTION_API.md # Decisão técnica
│   │   └── STACK_TECNOLOGICO.md     # Stack completo
│   ├── api/
│   │   └── API_REFERENCE.md         # Referência da API
│   └── guides/
│       └── QUICK_START.md           # Guia de início rápido
│
├── config/                    # Configurações
├── evolution-api/            # Evolution API (submodule/docker)
├── scripts/                  # Scripts utilitários
│   └── init-multiple-databases.sh
│
├── .gitignore
├── CONTRIBUTING.md           # Guia de contribuição
├── docker-compose.yml        # Orquestração de containers
├── LICENSE                   # Licença MIT
└── README.md                 # Documentação principal
```

## Componentes Principais

### Backend (Python + FastAPI)
- **API REST** com FastAPI
- **Autenticação** JWT
- **ORM** SQLAlchemy
- **Migrações** Alembic
- **IA** LangChain/LangGraph
- **Testes** pytest

### Frontend (Next.js + TypeScript)
- **Framework** Next.js 14 (App Router)
- **Linguagem** TypeScript
- **Styling** TailwindCSS
- **State** Zustand + React Query
- **Forms** React Hook Form + Zod

### Infraestrutura
- **Database** PostgreSQL
- **Cache** Redis
- **Vector DB** Qdrant
- **WhatsApp** Evolution API
- **Containers** Docker + Docker Compose

## Arquivos Criados

### Configuração
- ✅ docker-compose.yml
- ✅ .gitignore (root, backend, frontend)
- ✅ .env.example (backend, frontend)
- ✅ LICENSE (MIT)
- ✅ CONTRIBUTING.md

### Backend
- ✅ Dockerfile
- ✅ requirements.txt
- ✅ alembic.ini
- ✅ app/main.py
- ✅ app/core/config.py
- ✅ app/core/database.py
- ✅ app/models/models.py
- ✅ app/api/v1/router.py
- ✅ app/api/v1/endpoints/*.py (5 arquivos)
- ✅ tests/conftest.py
- ✅ tests/test_main.py
- ✅ alembic/env.py
- ✅ alembic/script.py.mako

### Frontend
- ✅ Dockerfile
- ✅ package.json
- ✅ tsconfig.json
- ✅ next.config.js
- ✅ tailwind.config.js
- ✅ src/app/layout.tsx
- ✅ src/app/page.tsx
- ✅ src/app/globals.css

### Documentação
- ✅ README.md (root, backend, frontend)
- ✅ docs/architecture/ARQUITETURA.md
- ✅ docs/architecture/DECISAO_EVOLUTION_API.md
- ✅ docs/architecture/STACK_TECNOLOGICO.md
- ✅ docs/api/API_REFERENCE.md
- ✅ docs/guides/QUICK_START.md

### Scripts
- ✅ scripts/init-multiple-databases.sh

## Próximos Passos

### 1. Inicialização
```bash
# Copiar variáveis de ambiente
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Editar e adicionar chaves de API
nano backend/.env

# Iniciar containers
docker-compose up -d
```

### 2. Desenvolvimento
- Implementar lógica de autenticação completa
- Criar adapter para Evolution API
- Desenvolver sistema de agentes com LangChain
- Implementar RAG para documentos
- Construir interface do dashboard
- Criar interface de chat em tempo real

### 3. Testes
- Escrever testes unitários
- Testes de integração
- Testes E2E

### 4. Deploy
- Configurar CI/CD
- Setup de produção
- Monitoramento e logs

## Decisões Técnicas Importantes

1. **Usar Evolution API como dependência** (não replicar)
   - Reduz tempo de desenvolvimento de 3-6 meses para 2-4 semanas
   - Manutenção do protocolo WhatsApp gerenciada pela comunidade

2. **Python + FastAPI para backend**
   - Excelente para IA/ML com LangChain
   - Performance adequada
   - Ecosystem rico

3. **Next.js 14 para frontend**
   - App Router moderno
   - SSR/SSG quando necessário
   - Excelente DX

4. **Docker Compose para desenvolvimento**
   - Ambiente consistente
   - Fácil onboarding
   - Isolamento de serviços

## Recursos

- **Documentação**: `/docs`
- **API Docs**: `http://localhost:8000/docs`
- **Quick Start**: `docs/guides/QUICK_START.md`
- **Arquitetura**: `docs/architecture/ARQUITETURA.md`
