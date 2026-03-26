# Frontend Neuralilux

Frontend do sistema de automação de conversas no WhatsApp com IA.

## 🎨 Design System

O projeto utiliza um design system completo baseado no Pencil com as seguintes cores:

- **Primary Purple**: #8B5CF6
- **Background Dark**: #0F0A1E
- **Background Card**: #1A1333
- **Text Primary**: #F9FAFB
- **Success Green**: #10B981
- **Error Red**: #EF4444

## 📁 Estrutura do Projeto

```
src/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Layout raiz
│   ├── page.tsx           # Página inicial (redirect)
│   ├── globals.css        # Estilos globais
│   ├── login/
│   │   └── page.tsx       # Página de login
│   ├── dashboard/
│   │   └── page.tsx       # Dashboard com métricas
│   └── chat/
│       └── page.tsx       # Interface de chat
├── components/
│   ├── ui/                # Componentes UI base
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Card.tsx
│   │   ├── Avatar.tsx
│   │   ├── Badge.tsx
│   │   └── SearchInput.tsx
│   ├── layout/            # Componentes de layout
│   │   └── Header.tsx
│   ├── dashboard/         # Componentes do dashboard
│   │   ├── MetricCard.tsx
│   │   ├── ActivityItem.tsx
│   │   └── BusinessMetricCard.tsx
│   └── chat/              # Componentes do chat
│       ├── ChatSidebar.tsx
│       ├── ChatListItem.tsx
│       ├── ChatHeader.tsx
│       ├── MessageBubble.tsx
│       ├── ChatInput.tsx
│       ├── MessageStatus.tsx
│       ├── TypingIndicator.tsx
│       └── EmptyChat.tsx
├── lib/
│   ├── utils.ts           # Utilitários (cn function)
│   └── constants.ts       # Constantes da aplicação
├── types/
│   ├── auth.ts            # Types de autenticação
│   ├── chat.ts            # Types de chat
│   └── dashboard.ts       # Types de dashboard
├── stores/
│   ├── useAuthStore.ts    # Store de autenticação
│   ├── useChatStore.ts    # Store de chat
│   └── useDashboardStore.ts # Store de dashboard
├── services/
│   ├── authService.ts     # Serviço de autenticação
│   ├── chatService.ts     # Serviço de chat
│   └── dashboardService.ts # Serviço de dashboard
└── middleware.ts          # Middleware de autenticação
```

## 🚀 Como Executar

### Desenvolvimento

```bash
cd frontend
npm install
npm run dev
```

O servidor estará disponível em `http://localhost:3000`

### Build de Produção

```bash
npm run build
npm start
```

### Type Checking

```bash
npm run type-check
```

## 📄 Páginas Implementadas

### 1. Login (`/login`)
- Formulário de login com validação
- Campos: Email/Usuário e Senha
- Checkbox "Manter-se conectado"
- Link "Esqueci a senha"
- Design com gradientes de fundo
- **Nota**: Footer de cadastro removido conforme solicitado

### 2. Dashboard (`/dashboard`)
- Header com logo, notificações e avatar
- **Visão Geral**: 4 cards de métricas principais
  - Conversas Ativas: 1,247 (+18%)
  - Tempo de Resposta: 2.3s (-24%)
  - Taxa de Conversão: 68% (+5%)
  - Satisfação (NPS): 8.7 (+0.3)
- **Métricas de Atendimento**: 3 cards de negócios
- **Atividade Recente**: Lista de atividades

### 3. Chat (`/chat`)
- **Sidebar Esquerda** (380px):
  - Título "Conversas"
  - Campo de busca
  - Lista de conversas com avatares
- **Área Principal**:
  - Header com avatar e botões de ação
  - Mensagens com status indicators
  - Input de mensagem
- **Status de mensagens**:
  - ⏰ Pendente (relógio)
  - ✓ Enviando (check único)
  - ✓✓ Enviada/Entregue (check duplo cinza)
  - ✓✓ Visualizada (check duplo roxo)

## 🛠️ Tecnologias Utilizadas

- **Next.js 14** - Framework React com App Router
- **TypeScript** - Tipagem estática
- **Tailwind CSS** - Estilização
- **Zustand** - Gerenciamento de estado
- **Lucide React** - Ícones
- **Axios** - Cliente HTTP

## 🎯 Status do Projeto

✅ Estrutura base completa
✅ Design system implementado
✅ Páginas principais criadas
✅ Componentes UI funcionais
✅ Gerenciamento de estado configurado
✅ Rotas protegidas
⏳ Integração com backend (pendente)
⏳ WebSocket para chat em tempo real (pendente)
