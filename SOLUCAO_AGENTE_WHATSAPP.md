# Solução do Problema do Agente WhatsApp

## 📋 Resumo Executivo

O agente WhatsApp estava retornando erro genérico devido a **problemas de conectividade com o LM Studio** rodando no host. Após correções, o agente funciona mas apresenta **inconsistência nas respostas**.

---

## 🔧 Correções Aplicadas

### 1. Conectividade Docker → LM Studio ✅

**Problema**: Worker em Docker não conseguia acessar `localhost:1234`

**Solução**:
```bash
# backend/.env
LM_STUDIO_URL=http://host.docker.internal:1235  # Era localhost:1234
LM_STUDIO_DISABLE_THINKING=true
```

### 2. Erro de Logging do Structlog ✅

**Problema**: `got multiple values for argument 'event'`

**Solução**:
```python
# app/super_agents/graph/nodes.py:46
logger.warning("Failed to emit event", error=str(exc), event_name=event)  # Era event=event
```

### 3. Modelo de Raciocínio vs Chat ✅

**Problema**: Modelo `qwen3.5-4b-claude-4.6-opus-reasoning-distilled-v2` retornava apenas thinking

**Solução**:
```bash
# backend/.env
WHATSAPP_AGENT_LM_STUDIO_MODEL=gemma-4-e2b-it  # Modelo de chat
```

---

## ✅ Status Atual

### Funcionando:
- ✅ Conectividade com LM Studio
- ✅ Classificação de intent (saudacao, cardapio, pedido)
- ✅ Execução de ferramentas (cardapio_tool, pedido_tool)
- ✅ Envio de mensagens via Evolution API
- ✅ Sem thinking vazando nas respostas

### Problemas Remanescentes:
- ⚠️ **Respostas inconsistentes**: Às vezes envia cardápio completo (255 chars), às vezes resposta genérica (97 chars)
- ⚠️ **Modelo gemma-4-e2b-it**: Não está seguindo consistentemente o contexto fornecido

---

## 📊 Evidências dos Logs

```
# Sucesso (cardápio enviado):
19:58:56 Intent classified: cardapio
19:58:56 Executing action: cardapio
19:58:56 Response sent: 255 chars ✅

# Falha (resposta genérica):
19:59:03 Intent classified: cardapio
19:59:03 Executing action: cardapio
19:59:03 Response sent: 97 chars ❌
```

---

## 🎯 Recomendações

### Opção 1: Usar Gemini API (Recomendado)
```bash
# backend/.env
WHATSAPP_AGENT_INFERENCE_PROVIDER=gemini
GEMINI_API_KEY=AIzaSyDqMkqDp-_RGUDec66HttEv8IOw6kuPkKU
GEMINI_MODEL=gemini-2.0-flash-lite
```

**Vantagens**:
- Modelo mais confiável e consistente
- Melhor seguimento de instruções
- Já configurado no projeto

### Opção 2: Testar Outros Modelos Locais
Modelos disponíveis no LM Studio:
- `bonsai-8b` (não testado)
- `qwen3.5-2b-claude-4.6-opus-reasoning-distilled` (modelo de raciocínio - não recomendado)

### Opção 3: Ajustar Prompts para Gemma
- Simplificar o SYSTEM_PROMPT
- Reduzir temperatura (0.2 → 0.1)
- Aumentar max_tokens

---

## 🧪 Como Testar

1. **Reiniciar worker**:
   ```bash
   docker compose restart worker
   ```

2. **Monitorar logs**:
   ```bash
   docker compose logs worker --follow | grep -E "Intent|response_length|cardapio"
   ```

3. **Enviar mensagens de teste**:
   - "Olá" → Deve responder saudação
   - "Quero ver o cardápio" → Deve enviar cardápio completo
   - "Quero uma pizza" → Deve adicionar ao pedido

---

## 📝 Arquivos Modificados

1. `backend/.env`:
   - LM_STUDIO_URL
   - LM_STUDIO_DISABLE_THINKING
   - WHATSAPP_AGENT_LM_STUDIO_MODEL

2. `app/super_agents/graph/nodes.py`:
   - Linha 46: Corrigido parâmetro `event_name`

---

## 🔍 Debugging

Para investigar problemas:

```bash
# Ver logs detalhados
docker compose logs worker --tail=500 | grep -A 10 "cardapio"

# Testar ferramenta diretamente
docker compose exec worker python3 -c "
from app.agents.tools.cardapio_tool import cardapio_tool
print(cardapio_tool.invoke({'query': 'resumo'}))
"

# Verificar conectividade LM Studio
curl http://localhost:1234/v1/models
```

---

## 📞 Próximos Passos

1. **Decisão**: Escolher entre Gemini API ou continuar com LM Studio
2. **Se Gemini**: Atualizar `.env` e reiniciar worker
3. **Se LM Studio**: Testar outros modelos ou ajustar prompts
4. **Validação**: Testar fluxo completo (saudação → cardápio → pedido → coleta → finalização)
