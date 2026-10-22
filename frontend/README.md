# Neuralilux Frontend

Dashboard e interface de chat em Next.js + TypeScript.

## Estrutura

```
frontend/
├── src/
│   ├── app/              # App Router (Next.js 16)
│   │   ├── dashboard/ chat/ instances/ pedidos/ estoque/ qr/ settings/ login/
│   │   └── layout.tsx
│   ├── components/       # Componentes React
│   ├── services/         # API clients
│   ├── hooks/            # Custom hooks
│   └── stores/           # Zustand stores
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

- **Framework**: Next.js 16 (App Router)
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
- `/pedidos` - Painel de Pedidos: a Company move o status e o Contact recebe o aviso no WhatsApp
- `/estoque` - Estoque do cardápio
- `/settings` - Configurações (Company, Agent e Gateways)
