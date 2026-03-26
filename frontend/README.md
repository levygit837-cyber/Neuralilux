# Neuralilux Frontend

Dashboard e interface de chat em Next.js + TypeScript.

## Estrutura

```
frontend/
├── src/
│   ├── app/              # App Router (Next.js 14)
│   │   ├── dashboard/
│   │   ├── chat/
│   │   └── layout.tsx
│   ├── components/       # Componentes React
│   ├── services/         # API clients
│   ├── hooks/            # Custom hooks
│   ├── store/            # Zustand stores
│   └── styles/           # Estilos globais
├── public/               # Assets estáticos
├── package.json
└── Dockerfile
```

## Setup Local

```bash
# Instalar dependências
npm install

# Configurar variáveis de ambiente
cp .env.example .env.local

# Iniciar servidor de desenvolvimento
npm run dev
```

## Scripts Disponíveis

```bash
npm run dev          # Desenvolvimento
npm run build        # Build de produção
npm start            # Iniciar produção
npm run lint         # Lint
npm run type-check   # Verificar tipos
```

## Tecnologias

- **Framework**: Next.js 14 (App Router)
- **Linguagem**: TypeScript
- **Styling**: TailwindCSS
- **State**: Zustand + React Query
- **Forms**: React Hook Form + Zod
- **Icons**: Lucide React

## Estrutura de Páginas

- `/` - Landing page
- `/dashboard` - Dashboard principal
- `/chat` - Interface de chat
- `/instances` - Gerenciar instâncias
- `/agents` - Gerenciar agentes
- `/settings` - Configurações
