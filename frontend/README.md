# Neuralilux Frontend

Painel e interface de chat em Next.js + TypeScript.

## Estrutura

```
frontend/
├── src/
│   ├── app/              # App Router (Next.js 16)
│   │   ├── login/        # única rota pública
│   │   ├── (app)/        # área autenticada: dashboard chat instances pedidos estoque qr settings
│   │   └── layout.tsx
│   ├── components/       # Componentes React, por área (chat, dashboard, estoque, settings...)
│   ├── services/         # Clientes da API; `http.ts` é a única porta para o backend
│   ├── hooks/            # Hooks (React Query, Socket.IO, sessão)
│   ├── stores/           # Stores Zustand
│   ├── lib/              # Constantes, chaves do React Query, CSP, sessão
│   ├── types/            # Tipos do domínio
│   └── proxy.ts          # Proxy do Next: valida a sessão e define a CSP
├── package.json
└── Dockerfile
```

## Setup Local

Requer Node 24 (`engines.node` no `package.json`; é a versão do CI).

```bash
# Instalar dependências (versões exatas, do package-lock.json)
npm ci

# Configurar variáveis de ambiente
cp .env.example .env.local

# Iniciar servidor de desenvolvimento
npm run dev
```

## Scripts Disponíveis

```bash
npm run dev          # Desenvolvimento
npm run build        # Build de produção
npm start            # Iniciar produção (no container: `node server.js` do build standalone)
npm run lint         # Lint
npm run type-check   # Verificar tipos
npm test             # Testes (Vitest)
```

## Dependências

Todas com versão exata. O `.npmrc` tem `save-exact=true`, então `npm install <pacote>` já grava a versão sem `^`. Para atualizar, troque a versão de propósito e regenere o `package-lock.json`. Para achar dependência sem uso: `npx depcheck@1.4.7` (o `.depcheckrc.json` ignora `postcss` e `autoprefixer`, que só o Tailwind carrega via `postcss.config.js`).

## Tecnologias

- **Framework**: Next.js 16 (App Router) e React 19
- **Linguagem**: TypeScript
- **Styling**: TailwindCSS, só tema dark. Os tokens de cor vivem como variáveis CSS em `src/app/globals.css` (`:root`) e são expostos em `tailwind.config.js` como `brand-*`, `primary-*`, `content-*` e `status-*`; não use hex nem cor fora desses nomes. O lint (`tailwindcss/no-custom-classname`) falha em classe inexistente. Variantes de componente com `class-variance-authority`; classes combinadas por `cn` (`clsx` + `tailwind-merge`).
- **State**: React Query (dados do backend) + Zustand (sessão, Instance selecionada, chat)
- **Realtime**: Socket.IO (`socket.io-client`)
- **Icons**: Phosphor (`@phosphor-icons/react`). É a única lib de ícones. Convenção para código novo: ícone decorativo (o texto ao lado já diz o que ele significa) leva `aria-hidden="true"`, porque o Phosphor não o põe por padrão; botão só com ícone leva `aria-label`.
- **QR Code**: `react-qr-code`
- **Testes**: Vitest, Testing Library e jsdom

Não há biblioteca de formulários nem de validação: os formulários usam estado do React e o backend valida (um 422 vira mensagem por campo em `services/http.ts`). Os gráficos do dashboard são SVG próprio, sem `recharts`.

## Dados do backend

Telas autenticadas leem e gravam pelo React Query. O `QueryClientProvider` fica em `src/app/(app)/layout.tsx` (via `components/providers/QueryProvider`); as chaves moram em `src/lib/queryKeys.ts`. Uma query só dispara com a sessão hidratada (`useSessionReady`), toda mutation invalida as queries que ela afeta, e o 401 continua encerrando a sessão em `services/http.ts`. O chat segue no store Zustand + Socket.IO, fora do React Query.

Toda chamada ao backend passa por `services/http.ts` (`apiRequest`, ou `apiFetch` quando o chamador precisa da `Response` crua, como o login). Nos serviços, só o `http.ts` chama `fetch`.

## Rotas

Definidas em `src/app`. Todas, menos `/login`, exigem sessão válida (`src/proxy.ts`).

- `/` - sem página: redireciona para `/dashboard` (com sessão) ou `/login`
- `/login` - Login
- `/dashboard` - Dashboard principal
- `/chat` - Interface de chat
- `/instances` - Gerenciar instâncias
- `/qr` - QR Code para conectar uma instância
- `/pedidos` - Painel de Pedidos: a Company move o status e o Contact recebe o aviso no WhatsApp
- `/estoque` - Estoque do cardápio
- `/settings` - Configurações (Company, Agent e Gateways)
- qualquer outra URL autenticada cai no 404 da área autenticada (`(app)/[...slug]`)
