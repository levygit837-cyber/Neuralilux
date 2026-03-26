# Guia de Execução - Neuralilux

## ✅ Implementação Concluída

Todos os arquivos foram criados com sucesso:

### Arquivos Criados/Modificados:

1. **Segurança e Autenticação**
   - ✅ `backend/app/core/security.py` - Hash de senha e JWT
   - ✅ `backend/app/api/v1/endpoints/auth.py` - Endpoints completos (register, login, me)

2. **Schemas Pydantic**
   - ✅ `backend/app/schemas/user.py`
   - ✅ `backend/app/schemas/company.py`
   - ✅ `backend/app/schemas/product.py`
   - ✅ `backend/app/schemas/__init__.py`

3. **Modelos do Banco de Dados**
   - ✅ `backend/app/models/models.py` - Adicionados: BusinessType, Company, ProductType, Product

4. **Services**
   - ✅ `backend/app/services/user_service.py`
   - ✅ `backend/app/services/company_service.py`
   - ✅ `backend/app/services/product_service.py`
   - ✅ `backend/app/services/__init__.py`

5. **Endpoints de API**
   - ✅ `backend/app/api/v1/endpoints/companies.py` - CRUD completo
   - ✅ `backend/app/api/v1/endpoints/products.py` - CRUD completo
   - ✅ `backend/app/api/v1/router.py` - Atualizado com novos endpoints

6. **Docker**
   - ✅ `docker-compose.yml` - Corrigido para usar `whatsplan/evolution:latest`

7. **Scripts**
   - ✅ `backend/scripts/seed_data.py` - Dados iniciais e usuário de teste

8. **Estrutura**
   - ✅ `backend/alembic/versions/` - Diretório criado

---

## 🚀 Próximos Passos para Execução

### 1. Iniciar os Containers Docker

```bash
cd /home/levybonito/Projetos/Neuralilux

# Parar containers antigos (se existirem)
docker-compose down

# Remover imagem antiga da Evolution API (se existir)
docker rmi atendai/evolution-api:latest 2>/dev/null || true

# Iniciar todos os containers
docker-compose up -d

# Verificar se todos estão rodando
docker-compose ps
```

### 2. Criar a Migração do Banco de Dados

```bash
# Entrar no container do backend
docker exec -it neuralilux-backend bash

# Dentro do container, gerar a migração
alembic revision --autogenerate -m "Initial schema with companies and products"

# Aplicar a migração
alembic upgrade head

# Sair do container
exit
```

### 3. Executar o Script de Seed Data

```bash
# Entrar no container do backend
docker exec -it neuralilux-backend bash

# Executar o script de seed
python scripts/seed_data.py

# Sair do container
exit
```

### 4. Verificar a API

Acesse a documentação interativa da API:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🧪 Testes da API

### 4.1. Registrar Novo Usuário

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "novo@usuario.com",
    "password": "senha123",
    "full_name": "Novo Usuário",
    "company_id": null
  }'
```

### 4.2. Login com Usuário de Teste

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=usuario@teste.com&password=teste123"
```

Resposta esperada:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 4.3. Obter Informações do Usuário Atual

```bash
# Substitua SEU_TOKEN pelo token recebido no login
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer SEU_TOKEN"
```

### 4.4. Listar Empresas

```bash
curl -X GET "http://localhost:8000/api/v1/companies" \
  -H "Authorization: Bearer SEU_TOKEN"
```

### 4.5. Criar Produto

```bash
curl -X POST "http://localhost:8000/api/v1/products" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "ID_DA_EMPRESA",
    "product_type_id": "ID_DO_TIPO",
    "name": "Pizza Margherita",
    "description": "Pizza tradicional com molho de tomate, mussarela e manjericão",
    "price": 45.90,
    "is_available": true,
    "stock_quantity": 100
  }'
```

---

## 📊 Estrutura do Banco de Dados

### Tabelas Criadas:

1. **business_types** - Tipos de empresa (Restaurante, Clínica, Loja, Serviços)
2. **companies** - Empresas com endereço, contatos, horários e config de IA
3. **product_types** - Tipos de produto (Comida, Bebida, Serviço, Produto Físico)
4. **products** - Produtos específicos por empresa
5. **users** - Usuários vinculados a empresas
6. **instances** - Instâncias WhatsApp (já existia)
7. **agents** - Agentes de IA (já existia)
8. **messages** - Mensagens (já existia)
9. **documents** - Documentos para RAG (já existia)

### Relacionamentos:

- Company → BusinessType (many-to-one)
- Company → User (one-to-many)
- Company → Product (one-to-many)
- Product → ProductType (many-to-one)
- User → Instance (one-to-many)
- User → Agent (one-to-many)

---

## 👤 Usuário de Teste

Após executar o seed data, você terá:

- **Email**: usuario@teste.com
- **Senha**: teste123
- **Nome**: Usuário Teste
- **Empresa**: Empresa Teste (Restaurante)

---

## 🔍 Verificar Banco de Dados

```bash
# Conectar ao PostgreSQL
docker exec -it neuralilux-postgres psql -U neuralilux -d neuralilux

# Listar tabelas
\dt

# Ver dados de business_types
SELECT * FROM business_types;

# Ver dados de companies
SELECT * FROM companies;

# Ver usuários
SELECT id, email, full_name, company_id FROM users;

# Sair
\q
```

---

## 🐛 Troubleshooting

### Erro: "relation does not exist"
- Execute a migração: `alembic upgrade head`

### Erro: "could not connect to server"
- Verifique se os containers estão rodando: `docker-compose ps`
- Reinicie os containers: `docker-compose restart`

### Erro: "email already registered"
- O usuário já existe no banco
- Use outro email ou faça login com o existente

### Evolution API não inicia
- Verifique se a imagem foi atualizada: `docker images | grep evolution`
- Deve mostrar `whatsplan/evolution` e não `atendai/evolution-api`

---

## 📝 Logs

```bash
# Ver logs de todos os containers
docker-compose logs -f

# Ver logs apenas do backend
docker-compose logs -f backend

# Ver logs da Evolution API
docker-compose logs -f evolution-api

# Ver logs do PostgreSQL
docker-compose logs -f postgres
```

---

## ✅ Checklist de Verificação

- [ ] Containers Docker iniciados
- [ ] Migração do banco executada
- [ ] Seed data executado
- [ ] API acessível em http://localhost:8000/docs
- [ ] Login com usuario@teste.com funciona
- [ ] Endpoint /auth/me retorna dados do usuário
- [ ] Endpoint /companies lista empresas
- [ ] Evolution API acessível em http://localhost:8080

---

## 🎯 Resumo das Mudanças

1. **Banco de Dados Central**: 4 novas tabelas (business_types, companies, product_types, products)
2. **Autenticação Completa**: Hash bcrypt + JWT funcionando
3. **APIs REST**: CRUD completo para empresas e produtos
4. **Docker Corrigido**: Imagem Evolution API atualizada para `whatsplan/evolution:latest`
5. **Dados Iniciais**: Script de seed com tipos padrão e usuário de teste
6. **Relacionamentos**: Usuários vinculados a empresas, produtos específicos por empresa

Tudo pronto para desenvolvimento! 🚀
