# Decisão: Usar Evolution API como Dependência

## Análise de Complexidade

### Sobre a Evolution API

A Evolution API é um sistema **moderadamente-a-altamente complexo** com:
- 2.623 commits
- 155 contribuidores
- 98.7% TypeScript
- Arquitetura de microserviços

### Componentes Principais

1. **Conectividade WhatsApp Dual**
   - Baileys (WhatsApp Web API)
   - Meta Cloud API oficial

2. **Arquitetura Event-Driven**
   - RabbitMQ, Kafka, SQS
   - WebSocket para tempo real

3. **Integrações**
   - Typebot, Chatwoot, Dify
   - OpenAI
   - S3/Minio para storage

4. **Stack Técnico**
   - Node.js + TypeScript
   - Prisma ORM
   - Docker + Prometheus + Grafana

## Estimativa de Replicação

**Tempo estimado**: 3-6 meses com equipe experiente

**Complexidades principais**:
- Implementação do protocolo WhatsApp (Baileys)
- Coordenação multi-protocolo
- Infraestrutura de streaming em tempo real
- Pipeline de processamento de mídia
- 8 integrações de terceiros
- Camadas de autenticação/segurança
- Sistema de telemetria

## Decisão: Usar como Dependência

### ✅ Vantagens

1. **Time-to-Market**: Reduz desenvolvimento de 3-6 meses para 2-4 semanas
2. **Manutenção**: Atualizações do WhatsApp gerenciadas pela comunidade
3. **Estabilidade**: Sistema testado em produção por milhares de usuários
4. **Features**: Acesso imediato a todas as funcionalidades
5. **Comunidade**: 155 contribuidores ativos
6. **Licença**: Apache 2.0 permite uso comercial

### ⚠️ Desvantagens

1. **Dependência Externa**: Mudanças no projeto podem afetar nosso sistema
2. **Overhead**: Funcionalidades que não usaremos
3. **Controle Limitado**: Menos flexibilidade em customizações profundas

### 🎯 Estratégia de Integração

**Modelo Recomendado**: **Microserviço Isolado**

```
┌─────────────────────────────────────────┐
│         Neuralilux Backend              │
│         (Python + FastAPI)              │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │   Agent Orchestration Layer      │  │
│  │   (LangChain/LangGraph)          │  │
│  └──────────────────────────────────┘  │
│              ↕                          │
│  ┌──────────────────────────────────┐  │
│  │   WhatsApp Service Adapter       │  │
│  │   (API Client)                   │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
              ↕ REST API
┌─────────────────────────────────────────┐
│      Evolution API Container            │
│      (Docker - Isolado)                 │
└─────────────────────────────────────────┘
```

### 📋 Implementação

1. **Deploy via Docker Compose**
   - Evolution API em container separado
   - Comunicação via REST API
   - Rede Docker isolada

2. **Adapter Pattern**
   - Criar camada de abstração no backend
   - Facilita migração futura se necessário
   - Isola lógica de negócio

3. **Webhook Integration**
   - Evolution API envia eventos via webhook
   - Nosso backend processa e envia para agentes IA
   - Resposta retorna via API da Evolution

## Conclusão

**Recomendação**: Usar Evolution API como dependência via Docker.

**Justificativa**: O custo-benefício é extremamente favorável. Replicar levaria 3-6 meses e exigiria manutenção contínua do protocolo WhatsApp. Usar como dependência permite focar no diferencial do produto: **orquestração inteligente de agentes IA**.

## Próximos Passos

1. Setup Evolution API via Docker Compose
2. Criar adapter no backend Python
3. Implementar sistema de webhooks
4. Desenvolver camada de agentes IA
5. Construir dashboard de gerenciamento
