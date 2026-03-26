# Neuralilux

Sistema de automação de conversas no WhatsApp com IA para empresas.

## 🎯 Objetivo

Conectar o WhatsApp de empresas e automatizar conversas com clientes usando agentes de IA personalizados. Foco principal em clínicas, lojas e vendedores que precisam de atendimento automatizado inteligente.

## 🏗️ Arquitetura

### Backend
- **Framework**: Python + FastAPI
- **Orquestração de Agentes**: LangChain/LangGraph
- **WhatsApp API**: Evolution API (integração via API)
- **Banco de Dados**: PostgreSQL
- **Cache**: Redis

### Frontend
- **Dashboard**: Gerenciamento de instâncias e configurações
- **Chat Interface**: Personalização de agentes e monitoramento em tempo real
- **Framework**: React/Next.js (a definir)

### IA e Agentes
- **Motor de IA**: OpenAI/Anthropic/Local LLMs
- **RAG**: Para empresas com grande volume de conteúdo
- **Personalização**: Alimentação com conteúdo específico da empresa

## 📁 Estrutura do Projeto

```
neuralilux/
├── backend/              # API Python + FastAPI
│   ├── app/
│   │   ├── api/         # Endpoints REST
│   │   ├── core/        # Configurações e utilitários
│   │   ├── models/      # Modelos de dados
│   │   ├── services/    # Lógica de negócio
│   │   └── agents/      # Agentes de IA
│   └── tests/
├── frontend/            # Dashboard e interface de chat
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── styles/
│   └── public/
├── docs/                # Documentação
│   ├── architecture/
│   ├── api/
│   └── guides/
├── config/              # Arquivos de configuração
├── evolution-api/       # Submodule ou Docker da Evolution API
└── scripts/             # Scripts de deploy e manutenção
```

## 🚀 Roadmap

### Fase 1: Fundação (Semanas 1-2)
- [ ] Setup do projeto e estrutura
- [ ] Integração com Evolution API
- [ ] Backend básico com FastAPI
- [ ] Autenticação e gerenciamento de usuários

### Fase 2: Core (Semanas 3-4)
- [ ] Sistema de agentes com LangChain
- [ ] Integração WhatsApp <-> IA
- [ ] Dashboard básico
- [ ] Gerenciamento de instâncias

### Fase 3: Inteligência (Semanas 5-6)
- [ ] Personalização de agentes
- [ ] Sistema RAG para documentos
- [ ] Interface de chat em tempo real
- [ ] Histórico de conversas

### Fase 4: Produção (Semanas 7-8)
- [ ] Testes e otimizações
- [ ] Deploy e CI/CD
- [ ] Documentação completa
- [ ] Monitoramento e logs

## 🔧 Tecnologias

- **Backend**: Python 3.11+, FastAPI, LangChain, SQLAlchemy
- **Frontend**: React/Next.js, TypeScript, TailwindCSS
- **Database**: PostgreSQL, Redis
- **WhatsApp**: Evolution API
- **IA**: OpenAI API, Anthropic Claude, LangChain
- **DevOps**: Docker, Docker Compose, GitHub Actions

## 📝 Licença

MIT
