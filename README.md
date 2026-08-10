<div align="center">

# Neuralilux

**Protótipo técnico de atendimento assistido por IA para operações no WhatsApp.**

*An AI-assisted WhatsApp operations prototype with agent tools, company-scoped retrieval and human supervision.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

## Navegação rápida

[Problema](#o-problema) · [Implementação](#o-que-está-implementado) · [Arquitetura](#arquitetura) · [Execução](#rodar-localmente) · [Limites](#limites-atuais) · [Guia para avaliadores](docs/reviewer-guide.md)

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
- regras e documentos por empresa, ingestão de conteúdo e recuperação via Qdrant;
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
   ├── PostgreSQL            ├── provedores de inferência + fallback
   ├── Redis / RabbitMQ      └── RAG por empresa / Qdrant
   │
   └── Socket.IO / REST ── dashboard Next.js
```

```text
backend/app/
├── agents/          # grafo, prompts, memória, outputs e tools
├── api/v1/          # autenticação, instâncias, conversas e configuração
├── rag/             # ingestão, recuperação e vector store
├── services/        # Evolution API, inferência, catálogo e tempo real
└── super_agents/    # workspace experimental de agente e tool runtime

frontend/src/
├── app/             # rotas do dashboard
├── components/      # chat, agente, métricas e configurações
├── services/        # clientes HTTP e Socket.IO
└── stores/          # estado de autenticação, chat e instâncias
```

## Rodar localmente

O frontend possui manifesto versionado e pode ser inspecionado isoladamente:

```bash
cp frontend/.env.example frontend/.env.local
cd frontend
npm install
npm run dev
```

O backend exige PostgreSQL, Redis, RabbitMQ, Qdrant e Evolution API, mas o snapshot público atual não
versiona um manifesto de dependências Python nem um `docker-compose.yml`. Por isso não há um comando
honesto e reproduzível para subir a jornada completa a partir de um clone limpo. Restaurar esses
manifestos e validar a instalação é uma pendência do projeto.

## Limites atuais

- o snapshot público não contém manifesto de dependências do backend nem Compose da infraestrutura;
- o frontend referencia `frontend/src/lib/authToken.ts`, mas esse arquivo não está versionado;
- endpoints de RAG e tickets ainda exigem reforço de isolamento e autorização por empresa;
- as suítes não foram reproduzidas em uma instalação limpa desta versão pública;
- dependências frontend e defaults de desenvolvimento precisam de revisão antes de qualquer deploy;
- a navegação móvel e a acessibilidade ainda não passaram por validação completa;
- nenhuma métrica de clientes, disponibilidade ou uso comercial é comprovada pelo repositório.

## Documentação

- [Guia para avaliadores](docs/reviewer-guide.md)
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
