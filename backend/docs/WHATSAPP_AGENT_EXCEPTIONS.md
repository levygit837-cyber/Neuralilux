# WhatsApp Agent Custom Exceptions

Este documento descreve as exceções customizadas do WhatsApp Agent, quando são lançadas e como resolver os problemas que elas indicam.

## Visão Geral

As exceções customizadas foram adicionadas para facilitar o debugging do fluxo do WhatsApp Agent. Cada exceção representa um tipo específico de falha no pipeline de processamento de mensagens.

## Exceções

### WhatsAppAgentError

**Descrição**: Exceção base para todos os erros do WhatsApp Agent.

**Quando é lançada**: Nunca diretamente - é a classe base para todas as outras exceções.

**Como resolver**: Capture exceções mais específicas para obter detalhes do problema.

---

### AgentNotEnabledError

**Descrição**: Lançada quando o agente não está habilitado para a instância.

**Quando é lançada**:
- Quando `instance.agent_enabled == False`
- No método `_try_process_with_agent` do `whatsapp_consumer.py`

**Contexto**:
```python
{
    "instance_id": "123",
    "instance_name": "my-instance",
    "conversation_id": "456"
}
```

**Como resolver**:
1. Verifique se o agente está habilitado para a instância
2. Use o endpoint `/api/v1/instances/{instance_id}/agent-status` para verificar o status
3. Use o endpoint `/api/v1/instances/{instance_id}/agent-status` (PATCH) para habilitar o agente
4. Ou use o frontend para ativar o agente no ChatHeader

**Exemplo de log**:
```
Agent disabled for this instance
instance_id=123 instance_name=my-instance
```

---

### AgentNotAssignedError

**Descrição**: Lançada quando nenhum agente está atribuído à instância.

**Quando é lançada**:
- Quando `instance.agent_id == None` e não há agent padrão disponível
- No método `_try_process_with_agent` do `whatsapp_consumer.py`

**Contexto**:
```python
{
    "instance_id": "123",
    "instance_name": "my-instance",
    "owner_id": "456",
    "conversation_id": "789"
}
```

**Como resolver**:
1. Crie um agent para o usuário (owner_id)
2. Ou crie um agent global (owner_id=None)
3. Atribua o agent à instância usando `/api/v1/instances/{instance_id}/agent-binding`
4. Ou use o frontend para selecionar um agente no ChatHeader

**Resolução automática**:
O sistema tenta resolver automaticamente o agent_id quando é None:
1. Primeiro busca um agent ativo do dono da instância
2. Se não encontrar, busca um agent global ativo
3. Se não encontrar nenhum, lança `AgentNotAssignedError`

**Exemplo de log**:
```
No agent assigned to this instance
instance_id=123 owner_id=456
No default agent found for instance
```

---

### AgentInactiveError

**Descrição**: Lançada quando o agente atribuído não existe ou está inativo.

**Quando é lançada**:
- Quando `instance.agent_id` aponta para um agent que não existe
- Quando o agent existe mas `is_active == False`
- No método `_try_process_with_agent` do `whatsapp_consumer.py`

**Contexto**:
```python
{
    "instance_id": "123",
    "instance_name": "my-instance",
    "agent_id": "456",
    "conversation_id": "789"
}
```

**Como resolver**:
1. Verifique se o agent existe no banco de dados
2. Verifique se o agent está ativo (`is_active == True`)
3. Se o agent foi deletado, atribua outro agent à instância
4. Use `/api/v1/instances/{instance_id}/agent-binding` para corrigir

**Exemplo de log**:
```
Agent not found or inactive
instance_id=123 agent_id=456
```

---

### MessageProcessingError

**Descrição**: Lançada quando ocorre um erro no processamento da mensagem.

**Quando é lançada**:
- Em erros genéricos de processamento no fluxo do agente
- Captura exceções que não são de um tipo específico conhecido

**Contexto**:
```python
{
    "conversation_id": "123",
    "correlation_id": "abc-123-def"
}
```

**Como resolver**:
1. Verifique o traceback completo nos logs
2. Identifique a causa raiz do erro
3. Corrija o problema específico (pode ser banco de dados, API externa, etc.)

**Exemplo de log**:
```
Message processing error
correlation_id=abc-123-def conversation_id=123
error_type=MessageProcessingError
```

---

### InferenceError

**Descrição**: Lançada quando a inferência via LM Studio falha.

**Quando é lançada**:
- Quando o LM Studio não está disponível
- Quando a requisição ao LM Studio falha
- Quando há timeout na requisição
- Quando o modelo retorna erro

**Contexto**:
```python
{
    "conversation_id": "123",
    "correlation_id": "abc-123-def",
    "intent": "cardapio"
}
```

**Como resolver**:
1. Verifique se o LM Studio está rodando em `http://localhost:1234`
2. Verifique se o modelo configurado está carregado no LM Studio
3. Verifique se há problemas de conectividade
4. Verifique os logs do LM Studio para mais detalhes

**Configuração**:
```python
LM_STUDIO_URL = "http://localhost:1234"
WHATSAPP_AGENT_LM_STUDIO_MODEL = "qwen3.5-4b-claude-4.6-opus-reasoning-distilled-v2"
```

**Exemplo de log**:
```
Inference error during intent classification
correlation_id=abc-123-def conversation_id=123
error=Connection refused
```

---

### EvolutionAPIError

**Descrição**: Lançada quando a comunicação com a Evolution API falha.

**Quando é lançada**:
- Quando não é possível enviar mensagem via Evolution API
- Quando a instância não está conectada
- Quando há erro na requisição HTTP

**Contexto**:
```python
{
    "instance_name": "my-instance",
    "remote_jid": "5511999999999@s.whatsapp.net",
    "response_length": 150
}
```

**Como resolver**:
1. Verifique se a instância está conectada ao WhatsApp
2. Verifique se o Evolution API está acessível
3. Verifique se o nome da instância está correto
4. Verifique os logs do Evolution API

**Exemplo de log**:
```
Evolution API communication error
correlation_id=abc-123-def instance_name=my-instance
error=Connection refused
```

---

### ContextLoadError

**Descrição**: Lançada quando falha ao carregar o contexto da conversa.

**Quando é lançada**:
- Quando não é possível carregar o histórico de mensagens
- Quando há erro ao buscar o pedido ativo
- No nó `load_context_node` do grafo

**Contexto**:
```python
{
    "conversation_id": "123",
    "correlation_id": "abc-123-def"
}
```

**Como resolver**:
1. Verifique se a conversa existe no banco de dados
2. Verifique se há problemas de conexão com o banco
3. Verifique se o histórico de mensagens está consistente
4. Verifique se há problemas no serviço de pedidos

**Exemplo de log**:
```
Failed to load conversation context
correlation_id=abc-123-def conversation_id=123
```

---

### IntentClassificationError

**Descrição**: Lançada quando falha a classificação da intenção da mensagem.

**Quando é lançada**:
- Quando o LLM não consegue classificar a intenção
- Quando há erro de inferência durante classificação
- Quando a resposta do LLM é inválida
- No nó `classify_intent_node` do grafo

**Contexto**:
```python
{
    "conversation_id": "123",
    "correlation_id": "abc-123-def"
}
```

**Como resolver**:
1. Verifique se o LM Studio está funcionando
2. Verifique se o prompt de classificação está correto
3. Verifique se há problemas no serviço de inferência
4. Ajuste o prompt se necessário

**Exemplo de log**:
```
Inference error during intent classification
correlation_id=abc-123-def conversation_id=123
error=Invalid JSON response
```

---

### ResponseGenerationError

**Descrição**: Lançada quando falha a geração da resposta.

**Quando é lançada**:
- Quando o LLM não consegue gerar uma resposta
- Quando há erro de inferência durante geração
- Quando a resposta gerada é vazia
- No nó `generate_response_node` do grafo

**Contexto**:
```python
{
    "conversation_id": "123",
    "correlation_id": "abc-123-def",
    "intent": "cardapio"
}
```

**Como resolver**:
1. Verifique se o LM Studio está funcionando
2. Verifique se o prompt de geração está correto
3. Verifique se o contexto está sendo montado corretamente
4. Ajuste o prompt ou o contexto se necessário

**Exemplo de log**:
```
Inference error during response generation
correlation_id=abc-123-def conversation_id=123
error=Empty response
```

---

### ToolExecutionError

**Descrição**: Lançada quando falha a execução de uma tool.

**Quando é lançada**:
- Quando uma tool não consegue executar sua função
- Quando há erro na chamada de uma tool
- Quando a tool retorna erro

**Contexto**:
```python
{
    "conversation_id": "123",
    "correlation_id": "abc-123-def",
    "tool_name": "whatsapp_send_message"
}
```

**Como resolver**:
1. Verifique qual tool falhou
2. Verifique os parâmetros passados para a tool
3. Verifique se a dependência externa da tool está funcionando
4. Corrija o problema específico da tool

**Exemplo de log**:
```
Tool execution error
correlation_id=abc-123-def tool_name=whatsapp_send_message
```

---

### ConversationNotFoundError

**Descrição**: Lançada quando a conversa não é encontrada.

**Quando é lançada**:
- Quando se tenta acessar uma conversa que não existe
- Quando o conversation_id é inválido

**Contexto**:
```python
{
    "conversation_id": "123",
    "correlation_id": "abc-123-def"
}
```

**Como resolver**:
1. Verifique se o conversation_id está correto
2. Verifique se a conversa existe no banco
3. Verifique se a conversa não foi deletada

**Exemplo de log**:
```
Conversation not found
correlation_id=abc-123-def conversation_id=123
```

---

### InstanceNotFoundError

**Descrição**: Lançada quando a instância não é encontrada.

**Quando é lançada**:
- Quando se tenta acessar uma instância que não existe
- Quando o instance_id é inválido

**Contexto**:
```python
{
    "instance_id": "123",
    "correlation_id": "abc-123-def"
}
```

**Como resolver**:
1. Verifique se o instance_id está correto
2. Verifique se a instância existe no banco
3. Verifique se a instância não foi deletada

**Exemplo de log**:
```
Instance not found
correlation_id=abc-123-def instance_id=123
```

---

## Correlation ID

Todas as exceções incluem um `correlation_id` nos logs para facilitar o tracing do fluxo completo de uma mensagem. O correlation_id é gerado no início do processamento e propagado através de todo o pipeline.

**Como usar**:
1. Quando houver um erro, anote o correlation_id do log
2. Filtre os logs por esse correlation_id para ver o fluxo completo
3. Isso ajuda a identificar onde exatamente o fluxo falhou

**Exemplo**:
```bash
# Filtrar logs por correlation_id
grep "correlation_id=abc-123-def" logs/app.log
```

---

## Debugging Guide

### Passo 1: Identificar a exceção
Verifique o log para ver qual exceção foi lançada. O tipo de exceção indica a categoria do problema.

### Passo 2: Verificar o contexto
Cada exceção inclui contexto relevante (instance_id, conversation_id, etc.). Use essas informações para investigar.

### Passo 3: Usar o correlation_id
Filtre todos os logs pelo correlation_id para ver o fluxo completo:
```bash
grep "correlation_id=<ID>" logs/app.log
```

### Passo 4: Seguir as instruções específicas
Cada exceção tem instruções específicas de resolução neste documento.

### Passo 5: Verificar dependências externas
Muitas exceções estão relacionadas a dependências externas:
- LM Studio (para InferenceError)
- Evolution API (para EvolutionAPIError)
- Banco de dados (para ContextLoadError, ConversationNotFoundError, etc.)

### Passo 6: Verificar configurações
Verifique se as configurações estão corretas:
- `LM_STUDIO_URL`
- `WHATSAPP_AGENT_LM_STUDIO_MODEL`
- `WHATSAPP_AGENT_INFERENCE_PROVIDER`

---

## Testes

Os testes E2E em `tests/test_whatsapp_agent_e2e.py` validam o funcionamento das exceções:
- `test_agent_custom_exceptions`: Valida que exceções customizadas são lançadas corretamente
- `test_agent_auto_resolution_no_agent_id`: Valida a resolução automática de agent_id

Para executar os testes:
```bash
pytest tests/test_whatsapp_agent_e2e.py -v -s -m e2e
```
