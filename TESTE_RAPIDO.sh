#!/bin/bash

echo "🧪 Testando API Neuralilux..."
echo ""

# Login
echo "1. Fazendo login..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=usuario@teste.com&password=teste123")

TOKEN=$(echo $RESPONSE | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Erro no login"
  exit 1
fi

echo "✅ Login bem-sucedido!"
echo "Token: ${TOKEN:0:50}..."
echo ""

# Obter dados do usuário
echo "2. Obtendo dados do usuário..."
USER_DATA=$(curl -s -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer $TOKEN")

echo "✅ Dados do usuário obtidos:"
echo "$USER_DATA"
echo ""

# Listar empresas
echo "3. Listando empresas..."
COMPANIES=$(curl -s -X GET "http://localhost:8000/api/v1/companies" \
  -H "Authorization: Bearer $TOKEN")

echo "✅ Empresas:"
echo "$COMPANIES"
echo ""

echo "🎉 Todos os testes passaram!"
