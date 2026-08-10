# Neuralilux Backend

API em Python/FastAPI para o protótipo Neuralilux de operações assistidas por IA no WhatsApp.

## Estado do snapshot público

Este diretório contém a implementação do backend, migrações e testes históricos, mas **não contém hoje um manifesto de dependências Python versionado nem um ambiente Compose completo**. O script `../start-backend.sh` ainda referencia `requirements.txt`, portanto não representa uma instalação reproduzível a partir de clone limpo.

Até que os manifestos sejam restaurados e validados, use este documento como mapa técnico — não como promessa de setup funcional.

## Estrutura

```text
backend/
├── app/
│   ├── api/v1/          # autenticação, empresas, instâncias e conversas
│   ├── agents/          # grafo, estado, prompts, tools e execução
│   ├── core/            # configuração, banco, segurança e compatibilidade
│   ├── models/          # modelos SQLAlchemy
│   ├── rag/             # ingestão, recuperação e Qdrant
│   ├── services/        # Evolution API, inferência e tempo real
│   ├── super_agents/    # runtime experimental de agentes/tools
│   └── main.py          # aplicação FastAPI + Socket.IO
├── alembic/             # migrações do domínio
├── tests/               # suíte histórica
├── .env.example         # contrato de configuração de desenvolvimento
└── Dockerfile
```

## Fluxo principal do agente

```text
Evolution API webhook
  → persistência da mensagem
  → WhatsAppAgent
  → LangGraph: handoff → validação → contexto → intenção
  → tool operacional opcional
  → geração de resposta
  → envio pela Evolution API
  → eventos de acompanhamento para o dashboard
```

Pontos iniciais para revisão:

- `app/agents/agent_executor.py`
- `app/agents/graph/whatsapp_graph.py`
- `app/agents/graph/nodes.py`
- `app/agents/tools/`
- `app/api/v1/`
- `app/rag/`
- `alembic/versions/`

## Serviços esperados pela implementação

A configuração atual referencia:

- PostgreSQL;
- Redis;
- RabbitMQ;
- Qdrant;
- Evolution API;
- um provider de inferência configurado, como Gemini, Vertex AI ou LM Studio.

Esses serviços e versões ainda precisam ser consolidados em um Compose reproduzível.

## Endpoints representativos

- `GET /health` — health check;
- `POST /api/v1/auth/login` — autenticação;
- `GET /api/v1/instances` — instâncias do WhatsApp;
- `POST /api/v1/messages/send` — envio de mensagem;
- webhooks da Evolution API sob `/api/v1/`;
- documentação OpenAPI em `/docs` quando a aplicação está operacional.

## Pendências para restaurar o setup

1. reconstruir e fixar um manifesto de dependências a partir dos imports e do ambiente conhecido;
2. versionar um lockfile;
3. criar Compose mínimo para PostgreSQL, Redis, RabbitMQ e Qdrant;
4. executar todas as migrações em banco vazio;
5. validar health, login, criação de empresa/instância e uma conversa sintética;
6. publicar os comandos somente depois dessa jornada passar em CI.

Consulte também o [guia para avaliadores](../docs/reviewer-guide.md) e o [README principal](../README.md).
