# Análise de Heurísticas e Keyword Matching - Neuralilux WhatsApp Agent

**Data**: 2026-03-28  
**Objetivo**: Identificar e remover todas as heurísticas de keyword matching e respostas fixas do agente WhatsApp

---

## 🔍 PROBLEMAS IDENTIFICADOS

### 1. **HEURÍSTICAS E RESPOSTAS FIXAS** (CRÍTICO)

#### Problema 1.1: `_direct_greeting_response()` (nodes.py L323-326)
```python
def _direct_greeting_response() -> str:
    return "😊 Olá! Posso te mostrar algumas categorias do cardápio ou começar sua comanda. O que você quer ver primeiro?"
```
- **Localização**: `backend/app/agents/graph/nodes.py:323-326`
- **Uso**: Linha 646 quando `intent == "saudacao"`
- **Problema**: Resposta de saudação completamente fixa, sem análise do LLM
- **Impacto**: Cliente sempre recebe a mesma mensagem, sem personalização ou contexto

#### Problema 1.2: `_safe_fallback_response()` (nodes.py L311-322)
```python
def _safe_fallback_response(flow_stage: str | None) -> str:
    if flow_stage == "explorando_cardapio":
        return "😊 Posso te mostrar algumas categorias do cardápio ou procurar um item específico."
    if flow_stage == "fluxo_comanda":
        return "😊 Posso seguir com sua comanda, mostrar o total ou iniciar a finalização."
    if flow_stage == "coletando_dados":
        return "😊 Pode me enviar o próximo dado para eu continuar seu pedido."
    if flow_stage == "confirmando_pedido":
        return "😊 Se estiver tudo certo, posso confirmar seu pedido agora."
    return "😊 Posso te ajudar com o cardápio, sua comanda ou a finalização do pedido."
```
- **Localização**: `backend/app/agents/graph/nodes.py:311-322`
- **Uso**: Linhas 779 e 782 quando o modelo não gera resposta
- **Problema**: Respostas fixas baseadas apenas em `flow_stage`, sem análise do contexto
- **Impacto**: Respostas genéricas que não consideram a mensagem do cliente

#### Problema 1.3: Retorno direto de cardápio (nodes.py L648-651)
```python
if intent == "cardapio" and cardapio_context:
    logger.info("Returning direct menu response", length=len(cardapio_context))
    return {"response": cardapio_context}
```
- **Localização**: `backend/app/agents/graph/nodes.py:648-651`
- **Problema**: Retorna diretamente o resultado da tool sem passar pelo LLM
- **Impacto**: Resposta não é formatada naturalmente, apenas dump da tool

#### Problema 1.4: Retorno direto de pedido (nodes.py L658-661)
```python
if intent in {"pedido", "status_pedido"} and cardapio_context:
    logger.info("Returning direct order response", length=len(cardapio_context), intent=intent)
    return {"response": cardapio_context}
```
- **Localização**: `backend/app/agents/graph/nodes.py:658-661`
- **Problema**: Retorna diretamente o resultado da tool sem passar pelo LLM
- **Impacto**: Resposta não é formatada naturalmente

#### Problema 1.5: Retorno direto de coleta de dados (nodes.py L663-667)
```python
if intent == "coleta_dados":
    output_data = state.get("output_data") or {}
    response = output_data.get("mensagem_formatada") or output_data.get("mensagem") or "Obrigado pelas informações!"
    logger.info("Returning direct data-collection response", length=len(response))
    return {"response": response}
```
- **Localização**: `backend/app/agents/graph/nodes.py:663-667`
- **Problema**: Retorna mensagem formatada ou fixa sem passar pelo LLM
- **Impacto**: Resposta não é natural, usa template fixo

---

### 2. **PROBLEMA COM CARDAPIO_TOOL**

#### Problema 2.1: Query malformada
- **Sintoma**: Erro "não foi possível 'listar_todos categoria'"
- **Causa**: O LLM está gerando queries malformadas como `"listar_todos categoria"` ao invés de `"categoria:<nome>"` ou `"todos"`
- **Formato esperado pela tool**:
  - `"listar_categorias"` - Lista categorias
  - `"categoria:<nome>"` - Busca por categoria específica
  - `"buscar:<termo>"` - Busca textual ampla
  - `"item:<nome>"` - Busca item específico
  - `"todos"` - Lista cardápio completo

#### Problema 2.2: Prompt de planejamento pouco claro
```python
MENU_QUERY_PLAN_PROMPT = """Analise a mensagem do cliente e responda SOMENTE com um JSON válido no formato:
{"query":"listar_categorias|todos|categoria:<nome>|buscar:<termo>|item:<nome>"}

Regras:
- Use "listar_categorias" quando o cliente quiser ver categorias, tipos ou seções.
- Use "listar_categorias" quando o cliente disser que quer pedir, mas ainda não tiver escolhido item.
- Use "todos" quando o cliente pedir o cardápio completo.
- Use "categoria:<nome>" quando o pedido for claramente sobre uma categoria específica.
- Use "item:<nome>" quando a pergunta for sobre um item específico.
- Use "buscar:<termo>" quando for uma busca textual ampla.
- Não escreva nada fora do JSON.

Mensagem: {message}
Histórico: {history}
"""
```
- **Problema**: Falta exemplos concretos, formato pode confundir o LLM
- **Solução**: Adicionar exemplos e simplificar formato

---

## 📋 PLANO DE CORREÇÃO

### Fase 1: Remoção de Heurísticas (PRIORIDADE MÁXIMA)

#### 1.1. Remover `_direct_greeting_response()`
- **Arquivo**: `backend/app/agents/graph/nodes.py`
- **Ação**: 
  - Deletar função (L323-326)
  - Remover uso na linha 646
  - Fazer saudação passar pelo LLM

#### 1.2. Remover `_safe_fallback_response()`
- **Arquivo**: `backend/app/agents/graph/nodes.py`
- **Ação**:
  - Deletar função (L311-322)
  - Remover usos nas linhas 779 e 782
  - Criar prompt de fallback para o LLM

#### 1.3. Remover retornos diretos
- **Arquivo**: `backend/app/agents/graph/nodes.py`
- **Ação**:
  - Remover retorno direto de cardápio (L648-651)
  - Remover retorno direto de pedido (L658-661)
  - Remover retorno direto de coleta (L663-667)
  - Fazer todas as respostas passarem pelo LLM

### Fase 2: Correção do Cardapio Tool

#### 2.1. Melhorar prompt de planejamento
- **Arquivo**: `backend/app/agents/graph/nodes.py`
- **Ação**:
  - Adicionar exemplos concretos ao `MENU_QUERY_PLAN_PROMPT`
  - Simplificar formato de query
  - Adicionar validação de query gerada

#### 2.2. Adicionar logs de debug
- **Arquivo**: `backend/app/agents/tools/cardapio_tool.py`
- **Ação**:
  - Adicionar log da query recebida
  - Adicionar log do resultado gerado

### Fase 3: Testes do Fluxo de Pedido

#### 3.1. Criar testes unitários
- **Arquivo**: `backend/unit_tests/test_order_flow_complete.py`
- **Testes**:
  - `test_greeting_flow` - Saudação natural
  - `test_menu_request_flow` - Solicitação de cardápio
  - `test_add_item_flow` - Adicionar item
  - `test_view_order_flow` - Ver comanda
  - `test_checkout_flow` - Fechar pedido
  - `test_complete_order_flow` - Fluxo completo

---

## ✅ CHECKLIST DE IMPLEMENTAÇÃO

### Remoção de Heurísticas
- [ ] Remover `_direct_greeting_response()`
- [ ] Remover `_safe_fallback_response()`
- [ ] Remover retorno direto de cardápio
- [ ] Remover retorno direto de pedido
- [ ] Remover retorno direto de coleta
- [ ] Atualizar testes existentes

### Correção do Cardapio Tool
- [ ] Melhorar `MENU_QUERY_PLAN_PROMPT` com exemplos
- [ ] Adicionar validação de query
- [ ] Adicionar logs de debug
- [ ] Testar queries malformadas

### Testes do Fluxo de Pedido
- [ ] Criar `test_greeting_flow`
- [ ] Criar `test_menu_request_flow`
- [ ] Criar `test_add_item_flow`
- [ ] Criar `test_view_order_flow`
- [ ] Criar `test_checkout_flow`
- [ ] Criar `test_complete_order_flow`
- [ ] Executar todos os testes
- [ ] Validar performance em tempo real

---

## 🎯 RESULTADO ESPERADO

Após as correções:

1. **Respostas Naturais**: Todas as respostas serão geradas pelo LLM, considerando contexto completo
2. **Sem Mensagens Fixas**: Nenhuma resposta será hardcoded ou baseada apenas em keywords
3. **Cardápio Funcional**: Tool de cardápio funcionará corretamente com queries bem formadas
4. **Fluxo Testado**: Fluxo completo de pedido terá cobertura de testes
5. **Performance Validada**: Modelo responderá naturalmente em todas as fases

---

## 📊 MÉTRICAS DE SUCESSO

- ✅ 0 respostas fixas no código
- ✅ 0 keyword matching
- ✅ 100% das respostas passando pelo LLM
- ✅ Cardápio funcionando sem erros
- ✅ Fluxo de pedido com >80% cobertura de testes
- ✅ Tempo de resposta <3s em 95% dos casos