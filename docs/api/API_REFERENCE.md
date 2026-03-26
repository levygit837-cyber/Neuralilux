# API Reference - Neuralilux

## Base URL

```
Development: http://localhost:8000
Production: https://api.neuralilux.com
```

## Autenticação

Todas as rotas (exceto `/auth/login` e `/auth/register`) requerem autenticação via JWT Bearer token.

```bash
Authorization: Bearer <token>
```

## Endpoints

### Autenticação

#### POST /api/v1/auth/register
Registrar novo usuário.

**Request Body:**
```json
{
  "email": "usuario@exemplo.com",
  "password": "senha-forte-123",
  "full_name": "Nome Completo"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "email": "usuario@exemplo.com",
  "full_name": "Nome Completo",
  "is_active": true
}
```

#### POST /api/v1/auth/login
Fazer login e obter token.

**Request Body:**
```json
{
  "username": "usuario@exemplo.com",
  "password": "senha-forte-123"
}
```

**Response:** `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### GET /api/v1/auth/me
Obter informações do usuário atual.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "email": "usuario@exemplo.com",
  "full_name": "Nome Completo",
  "is_active": true,
  "created_at": "2024-01-01T00:00:00Z"
}
```

---

### Instâncias WhatsApp

#### GET /api/v1/instances
Listar todas as instâncias do usuário.

**Query Parameters:**
- `skip` (int): Paginação - itens para pular
- `limit` (int): Paginação - limite de itens

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "name": "Minha Loja",
    "phone_number": "5511999999999",
    "status": "connected",
    "agent_id": "uuid",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

#### POST /api/v1/instances
Criar nova instância WhatsApp.

**Request Body:**
```json
{
  "name": "Minha Loja",
  "agent_id": "uuid"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "Minha Loja",
  "evolution_instance_id": "instance-123",
  "status": "disconnected",
  "qr_code": "data:image/png;base64,..."
}
```

#### GET /api/v1/instances/{instance_id}
Obter detalhes de uma instância.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "name": "Minha Loja",
  "phone_number": "5511999999999",
  "status": "connected",
  "agent": {
    "id": "uuid",
    "name": "Agente Vendas"
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

#### PUT /api/v1/instances/{instance_id}
Atualizar instância.

**Request Body:**
```json
{
  "name": "Nova Loja",
  "agent_id": "uuid"
}
```

#### DELETE /api/v1/instances/{instance_id}
Deletar instância.

**Response:** `204 No Content`

#### GET /api/v1/instances/{instance_id}/qrcode
Obter QR Code para conexão.

**Response:** `200 OK`
```json
{
  "qr_code": "data:image/png;base64,..."
}
```

---

### Agentes de IA

#### GET /api/v1/agents
Listar todos os agentes.

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "name": "Agente Vendas",
    "description": "Agente para vendas",
    "model": "gpt-4-turbo-preview",
    "is_active": true
  }
]
```

#### POST /api/v1/agents
Criar novo agente.

**Request Body:**
```json
{
  "name": "Agente Vendas",
  "description": "Agente especializado em vendas",
  "system_prompt": "Você é um assistente de vendas...",
  "model": "gpt-4-turbo-preview",
  "temperature": 70,
  "max_tokens": 1000,
  "use_rag": false
}
```

**Response:** `201 Created`

#### GET /api/v1/agents/{agent_id}
Obter detalhes do agente.

#### PUT /api/v1/agents/{agent_id}
Atualizar agente.

#### DELETE /api/v1/agents/{agent_id}
Deletar agente.

#### POST /api/v1/agents/{agent_id}/train
Treinar agente com documentos.

**Request Body:**
```json
{
  "documents": ["file1.pdf", "file2.txt"]
}
```

#### POST /api/v1/agents/{agent_id}/test
Testar agente com mensagem.

**Request Body:**
```json
{
  "message": "Olá, quanto custa o produto X?"
}
```

**Response:** `200 OK`
```json
{
  "response": "O produto X custa R$ 99,90..."
}
```

---

### Mensagens

#### GET /api/v1/messages
Listar mensagens.

**Query Parameters:**
- `instance_id` (uuid): Filtrar por instância
- `remote_jid` (string): Filtrar por contato
- `direction` (string): incoming ou outgoing
- `skip` (int): Paginação
- `limit` (int): Limite

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "content": "Olá!",
    "direction": "incoming",
    "status": "read",
    "timestamp": "2024-01-01T00:00:00Z"
  }
]
```

#### POST /api/v1/messages/send
Enviar mensagem.

**Request Body:**
```json
{
  "instance_id": "uuid",
  "remote_jid": "5511999999999@s.whatsapp.net",
  "content": "Olá! Como posso ajudar?"
}
```

#### GET /api/v1/messages/conversation/{phone_number}
Obter histórico de conversa.

**Response:** `200 OK`
```json
{
  "contact": "5511999999999",
  "messages": [...]
}
```

---

### Webhooks

#### POST /api/v1/webhooks/evolution
Webhook para receber eventos da Evolution API.

**Request Body:**
```json
{
  "event": "messages.upsert",
  "instance": "instance-123",
  "data": {
    "key": {
      "remoteJid": "5511999999999@s.whatsapp.net",
      "fromMe": false,
      "id": "message-id"
    },
    "message": {
      "conversation": "Olá!"
    }
  }
}
```

---

## Códigos de Status

- `200 OK` - Sucesso
- `201 Created` - Recurso criado
- `204 No Content` - Sucesso sem conteúdo
- `400 Bad Request` - Requisição inválida
- `401 Unauthorized` - Não autenticado
- `403 Forbidden` - Sem permissão
- `404 Not Found` - Recurso não encontrado
- `422 Unprocessable Entity` - Validação falhou
- `500 Internal Server Error` - Erro no servidor

## Rate Limiting

- 60 requisições por minuto por usuário
- Header `X-RateLimit-Remaining` indica requisições restantes

## Paginação

Endpoints que retornam listas suportam paginação:

```
GET /api/v1/messages?skip=0&limit=20
```

## Erros

Formato padrão de erro:

```json
{
  "detail": "Mensagem de erro descritiva"
}
```
