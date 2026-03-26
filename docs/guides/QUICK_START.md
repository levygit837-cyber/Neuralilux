# Guia de Início Rápido - Neuralilux

## Pré-requisitos

- Docker e Docker Compose instalados
- Python 3.11+ (para desenvolvimento local)
- Node.js 20+ (para desenvolvimento local)
- Chaves de API (OpenAI ou Anthropic)

## Setup Rápido com Docker

### 1. Clone e Configure

```bash
# Clone o repositório
git clone <repository-url>
cd Neuralilux

# Copie os arquivos de ambiente
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Edite backend/.env e adicione suas chaves de API
nano backend/.env
```

### 2. Configure as Variáveis de Ambiente

**Backend (.env)**:
```bash
# Obrigatório: Adicione pelo menos uma chave de API
OPENAI_API_KEY=sk-your-key-here
# OU
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Altere as senhas padrão
SECRET_KEY=seu-secret-key-forte-aqui
EVOLUTION_API_KEY=sua-chave-evolution-api
```

### 3. Inicie os Serviços

```bash
# Inicie todos os containers
docker-compose up -d

# Verifique os logs
docker-compose logs -f
```

### 4. Acesse as Aplicações

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Evolution API**: http://localhost:8080

## Desenvolvimento Local (Sem Docker)

### Backend

```bash
cd backend

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instale dependências
pip install -r requirements.txt

# Configure .env
cp .env.example .env
nano .env

# Inicie PostgreSQL e Redis (via Docker ou local)
docker-compose up -d postgres redis qdrant

# Execute migrações
alembic upgrade head

# Inicie o servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend

# Instale dependências
npm install

# Configure .env
cp .env.example .env.local

# Inicie o servidor de desenvolvimento
npm run dev
```

## Primeiro Uso

### 1. Criar Usuário

```bash
# Via API (usando curl)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "seu@email.com",
    "password": "senha-forte",
    "full_name": "Seu Nome"
  }'
```

### 2. Fazer Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=seu@email.com&password=senha-forte"
```

### 3. Criar Instância WhatsApp

1. Acesse o dashboard em http://localhost:3000
2. Faça login com suas credenciais
3. Clique em "Nova Instância"
4. Escaneie o QR Code com seu WhatsApp
5. Aguarde a conexão

### 4. Criar Agente de IA

1. Vá para "Agentes" no menu
2. Clique em "Novo Agente"
3. Configure:
   - Nome do agente
   - Prompt do sistema
   - Modelo de IA (GPT-4 ou Claude)
   - Temperatura
4. Salve o agente

### 5. Vincular Agente à Instância

1. Vá para "Instâncias"
2. Selecione sua instância
3. Escolha o agente criado
4. Salve

Pronto! Seu sistema está funcionando. Mensagens recebidas no WhatsApp serão automaticamente processadas pelo agente de IA.

## Comandos Úteis

### Docker

```bash
# Ver logs de um serviço específico
docker-compose logs -f backend

# Reiniciar um serviço
docker-compose restart backend

# Parar todos os serviços
docker-compose down

# Parar e remover volumes (CUIDADO: apaga dados)
docker-compose down -v

# Reconstruir imagens
docker-compose build --no-cache
```

### Backend

```bash
# Criar nova migração
alembic revision --autogenerate -m "descrição"

# Aplicar migrações
alembic upgrade head

# Reverter migração
alembic downgrade -1

# Executar testes
pytest

# Verificar cobertura
pytest --cov=app tests/
```

### Frontend

```bash
# Build de produção
npm run build

# Iniciar produção
npm start

# Lint
npm run lint

# Type check
npm run type-check
```

## Troubleshooting

### Evolution API não conecta

```bash
# Verifique os logs
docker-compose logs evolution-api

# Reinicie o container
docker-compose restart evolution-api

# Verifique se a porta 8080 está livre
netstat -an | grep 8080
```

### Backend não inicia

```bash
# Verifique se o PostgreSQL está rodando
docker-compose ps postgres

# Verifique as variáveis de ambiente
docker-compose exec backend env | grep DATABASE

# Teste a conexão com o banco
docker-compose exec backend python -c "from app.core.database import engine; print(engine.connect())"
```

### Frontend não carrega

```bash
# Limpe o cache
rm -rf frontend/.next
rm -rf frontend/node_modules

# Reinstale dependências
cd frontend && npm install

# Reconstrua
npm run build
```

## Próximos Passos

1. Leia a [Documentação de Arquitetura](docs/architecture/ARQUITETURA.md)
2. Explore a [API Documentation](http://localhost:8000/docs)
3. Configure RAG para documentos da empresa
4. Personalize os agentes de IA
5. Configure webhooks adicionais

## Suporte

- Documentação: `/docs`
- Issues: GitHub Issues
- Email: suporte@neuralilux.com
