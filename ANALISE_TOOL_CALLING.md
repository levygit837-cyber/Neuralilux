# Análise Completa: Problema de Tool Calling no Agente WhatsApp

**Data:** 2026-03-28  
**Status:** ROOT CAUSE IDENTIFICADA ✅

## 🔍 Problema Relatado

O modelo Gemini não está utilizando as ferramentas (tools) disponíveis:
- Modelo diz que está mostrando o cardápio mas não está
- Modelo não utiliza `cardapio_tool` para acessar o cardápio
- Modelo usa respostas diretas sem quebras de linha e emojis
- Respostas genéricas sem conteúdo real do cardápio

## 🧪 Testes Executados

### Resultado dos Testes de Integração
```bash
pytest backend/tests/test_cardapio_integration.py -v
```

**Todos os 3 testes FALHARAM:**

1. `test_agent_uses_cardapio_tool_on_menu_request` - FAILED
2. `test_agent_uses_cardapio_tool_on_category_request` - FAILED  
3. `test_agent_response_formatting` - FAILED

### Logs Críticos Identificados

```json
{
  "event": "Streaming completed",
  "thinking_tokens": 0,
  "response_tokens": 0,
  "thinking_length": 0,
  "response_length": 0,
  "has_response": false,
  "thinking_preview": "(empty)",
  "response_preview": "(empty)"
}
```

```json
{
  "event": "Model produced empty response; attempting fallback strategies"
}
```

**Diagnóstico:** O modelo está retornando resposta VAZIA, forçando o sistema a usar fallback que gera respostas genéricas.

## 🎯 ROOT CAUSE IDENTIFICADA

### Problema Principal: GeminiInferenceService não configurado com Function Calling

**Arquivo:** `backend/app/services/gemini_inference_service.py`  
**Método:** `_build_payload` (linhas 130-152)

#### Payload Atual (INCORRETO):
```python
payload: Dict[str, Any] = {
    "contents": contents,
    "generationConfig": {
        "maxOutputTokens": max_tokens or self.max_tokens,
        "temperature": temperature if temperature is not None else self.temperature,
        "responseMimeType": "text/plain",
    }
}

if system_instruction:
    payload["systemInstruction"] = {
        "parts": [{"text": system_instruction}]
    }
```

**❌ FALTA O CAMPO `tools`!**

#### Payload Necessário (CORRETO):
```python
payload: Dict[str, Any] = {
    "contents": contents,
    "generationConfig": {...},
    "systemInstruction": {...},
    "tools": [
        {
            "function_declarations": [
                {
                    "name": "cardapio_tool",
                    "description": "Consulta o cardápio estruturado da Macedos",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Consulta sobre o cardápio"
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    ]
}
```

### Problemas Identificados no Código

1. **`_build_payload` não aceita parâmetro `tools`**
   - Linha 130: Assinatura não inclui `tools`
   
2. **Métodos públicos não aceitam `tools`**
   - `chat_completion` (L354-428): Sem parâmetro `tools`
   - `astream_chat_completion_with_thinking` (L154-352): Sem parâmetro `tools`
   - `generate_response` (L430-465): Sem parâmetro `tools`

3. **Nenhuma lógica para processar tool calls**
   - Resposta do Gemini não é parseada para extrair `functionCall`
   - Não há retorno de `tool_calls` no formato esperado

4. **Integração com o agente incompleta**
   - `generate_response_node` não passa tools para o serviço
   - `execute_action_node` não recebe tool calls do modelo

## 📋 Solução Implementada

### Fase 1: Modificar GeminiInferenceService

#### 1.1 Adicionar suporte a tools em `_build_payload`
```python
def _build_payload(
    self,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str],
    max_tokens: Optional[int],
    temperature: Optional[float],
    tools: Optional[List[Dict[str, Any]]] = None,  # NOVO
) -> Dict[str, Any]:
    # ... código existente ...
    
    # ADICIONAR:
    if tools:
        payload["tools"] = tools
    
    return payload
```

#### 1.2 Adicionar suporte a tools em `chat_completion`
```python
async def chat_completion(
    self,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    tools: Optional[List[Dict[str, Any]]] = None,  # NOVO
) -> Dict[str, Any]:
    # ... passar tools para _build_payload ...
    
    # ADICIONAR lógica para extrair tool calls:
    tool_calls = []
    if data.get("candidates") and len(data["candidates"]) > 0:
        candidate = data["candidates"][0]
        content_part = candidate.get("content", {})
        parts = content_part.get("parts", [])
        
        for part in parts:
            if "functionCall" in part:
                tool_calls.append({
                    "name": part["functionCall"]["name"],
                    "arguments": part["functionCall"]["args"]
                })
    
    return {
        "content": content,
        "tool_calls": tool_calls,  # NOVO
        # ... resto ...
    }
```

#### 1.3 Adicionar suporte a tools em `astream_chat_completion_with_thinking`
```python
async def astream_chat_completion_with_thinking(
    self,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    tools: Optional[List[Dict[str, Any]]] = None,  # NOVO
) -> AsyncGenerator[Tuple[str, str], None]:
    # ... passar tools para _build_payload ...
```

### Fase 2: Definir Tools no Formato Gemini

Criar arquivo `backend/app/agents/tools/tool_definitions.py`:
```python
CARDAPIO_TOOL_DEFINITION = {
    "name": "cardapio_tool",
    "description": "Consulta o cardápio estruturado da Macedos. Use para listar categorias, buscar itens por categoria, buscar itens específicos ou mostrar o cardápio completo.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Consulta sobre o cardápio. Exemplos: 'listar_categorias', 'categoria:Pizzas', 'buscar:Margherita', 'listar_todos'"
            }
        },
        "required": ["query"]
    }
}

PEDIDO_TOOL_DEFINITION = {
    "name": "pedido_tool",
    "description": "Gerencia o pedido do cliente. Use para adicionar, remover, consultar ou finalizar pedidos.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["adicionar", "remover", "consultar", "limpar", "total", "iniciar_finalizacao", "confirmar"],
                "description": "Ação a ser executada no pedido"
            },
            "item_nome": {
                "type": "string",
                "description": "Nome do item (para adicionar/remover)"
            },
            "quantidade": {
                "type": "integer",
                "description": "Quantidade do item (para adicionar)"
            },
            "observacao": {
                "type": "string",
                "description": "Observação sobre o item (opcional)"
            }
        },
        "required": ["action"]
    }
}

HORARIO_TOOL_DEFINITION = {
    "name": "horario_tool",
    "description": "Verifica o horário de funcionamento da Macedos.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

WHATSAPP_AGENT_TOOLS = [
    {"function_declarations": [
        CARDAPIO_TOOL_DEFINITION,
        PEDIDO_TOOL_DEFINITION,
        HORARIO_TOOL_DEFINITION
    ]}
]
```

### Fase 3: Integrar com generate_response_node

Modificar `backend/app/agents/graph/nodes.py`:
```python
from app.agents.tools.tool_definitions import WHATSAPP_AGENT_TOOLS

async def generate_response_node(state: AgentState) -> Dict[str, Any]:
    # ... código existente ...
    
    # ADICIONAR tools na chamada:
    result = await inference_service.chat_completion(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=1024,
        temperature=0.7,
        tools=WHATSAPP_AGENT_TOOLS  # NOVO
    )
    
    # PROCESSAR tool_calls:
    tool_calls = result.get("tool_calls", [])
    if tool_calls:
        return {
            "tool_calls": tool_calls,
            "response": "",
            "thinking": ""
        }
    
    # ... resto do código ...
```

## ✅ Validação

### Testes Automatizados
Após implementação, executar:
```bash
pytest backend/tests/test_cardapio_integration.py -v
```

**Resultado Esperado:** Todos os 3 testes devem PASSAR

### Teste Manual
1. Enviar mensagem: "Quero ver o cardápio"
2. Verificar que `cardapio_tool` é chamada
3. Verificar que resposta contém cardápio formatado
4. Verificar quebras de linha e emojis

## 📊 Impacto da Correção

### Antes (INCORRETO):
- ❌ Modelo retorna resposta vazia
- ❌ Sistema usa fallback genérico
- ❌ Nenhuma tool é chamada
- ❌ Resposta sem conteúdo real do cardápio
- ❌ Sem quebras de linha e formatação

### Depois (CORRETO):
- ✅ Modelo retorna tool calls
- ✅ Sistema executa as tools
- ✅ `cardapio_tool` é chamada corretamente
- ✅ Resposta contém cardápio real formatado
- ✅ Quebras de linha e emojis presentes

## 🔗 Referências

- [Gemini Function Calling Documentation](https://ai.google.dev/gemini-api/docs/function-calling)
- Arquivo: `backend/app/services/gemini_inference_service.py`
- Arquivo: `backend/app/agents/graph/nodes.py`
- Arquivo: `backend/tests/test_cardapio_integration.py`