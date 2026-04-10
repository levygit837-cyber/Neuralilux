# Correção de Delay no Streaming de Mensagens

## Problema Identificado

O sistema apresentava delay de 3-5 minutos para receber mensagens completas do agente devido a **streaming falso**:

1. **Acumulação de tokens**: O método `stream_chat_completion_with_tools` acumulava TODOS os tokens de resposta em memória
2. **Chunking artificial**: Após receber a resposta completa (3-5 min), fazia chunking artificial em pedaços de 20 caracteres
3. **Falta de callback**: Não havia callback `on_response_token` para emitir tokens em tempo real

## Arquivos Corrigidos

### 1. `backend/app/services/inference_service.py`

**Mudanças:**

- **Linha 645**: Adicionado parâmetro `on_response_token` na assinatura do método
- **Linhas 708-755**: Modificado `_process_content_token` para emitir tokens de resposta em tempo real via callback
- **Linhas 757-767**: Modificado `_finalize_tag_buffer` para emitir tokens finais via callback

**Comportamento anterior:**
```python
# Acumulava tudo
content_parts.append(prefix)  # Apenas acumulava
# ...
final_content = "".join(content_parts)  # Retornava tudo no final
```

**Comportamento novo:**
```python
# Acumula E emite em tempo real
content_parts.append(prefix)
if on_response_token is not None:
    await on_response_token(prefix)  # Emite imediatamente
```

### 2. `backend/app/super_agents/graph/nodes.py`

**Mudanças:**

- **Linhas 272-310**: Refatorado para usar callback `on_response_token` e emitir tokens conforme chegam do LLM
- **Removido**: Loop artificial de chunking (linhas 298-303 antigas)

**Comportamento anterior:**
```python
# Esperava resposta completa (3-5 min)
final = await inference_svc.stream_chat_completion_with_tools(...)
response_text = final.get("content")  # Bloqueava aqui

# Chunking artificial DEPOIS de ter tudo
for i in range(0, len(response_text), 20):
    chunk = response_text[i: i + 20]
    await _emit(..., "response_token", {"token": chunk})
```

**Comportamento novo:**
```python
# Define callback que emite tokens em tempo real
async def _on_final_response(token: str) -> None:
    await _emit(..., "response_token", {"token": token})

# Emite response_start ANTES do streaming
await _emit(..., "response_start")

# Streaming real - tokens chegam conforme LLM gera
final = await inference_svc.stream_chat_completion_with_tools(
    ...,
    on_response_token=_on_final_response,  # Callback em tempo real
)
```

## Fluxo Corrigido

### Antes (QUEBRADO):
```
LLM gera token → 
inference_service ACUMULA em array (3-5 min) → 
Retorna string completa → 
nodes.py faz chunking artificial → 
Redis → Socket.IO → Frontend
```

### Depois (CORRETO):
```
LLM gera token → 
inference_service emite via callback IMEDIATAMENTE → 
nodes.py recebe e emite via Redis → 
Socket.IO → Frontend (tempo real)
```

## Componentes que JÁ Funcionavam Corretamente

1. **Realtime Event Bus** (`realtime_event_bus.py`): Publica eventos via Redis sem delay
2. **Socket Service** (`socket_service.py`): Emite eventos Socket.IO imediatamente
3. **Gemini Inference Service** (`gemini_inference_service.py`): Já fazia streaming real com yield
4. **WhatsApp Agent** (`agents/graph/nodes.py`): Já emitia tokens em tempo real

## Resultado Esperado

- ✅ Tokens de resposta chegam ao frontend em **tempo real** (< 100ms)
- ✅ Usuário vê a resposta sendo escrita conforme o LLM gera
- ✅ Sem delay de 3-5 minutos
- ✅ Experiência fluida e responsiva

## Teste

Para testar, envie uma mensagem ao agente e observe:
1. Thinking tokens devem aparecer imediatamente
2. Response tokens devem aparecer conforme são gerados (não todos de uma vez)
3. Tempo total de resposta deve ser proporcional ao tamanho da resposta (não fixo em 3-5 min)
