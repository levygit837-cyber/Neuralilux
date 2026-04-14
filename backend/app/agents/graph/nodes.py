"""Graph nodes for the WhatsApp agent."""
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict
import structlog

from app.agents.state import AgentState
from app.agents.outputs.coleta_output import format_coleta
from app.agents.outputs.pedido_output import format_comanda
from app.agents.prompts import INTENT_CLASSIFICATION_PROMPT, RESPONSE_GENERATION_PROMPT, SYSTEM_PROMPT
from app.agents.message_variations import (
    get_saudacao,
    get_fallback_message,
    get_mensagem_sem_comanda,
    get_pedido_vazio_message,
)
from app.agents.llm_responses import (
    generate_saudacao_with_fallback,
    generate_fallback_response_with_fallback,
    get_cardapio_context_with_variations,
)
from app.agents.memory.history_loader import load_conversation_history
from app.agents.tools.pedido_tool import set_active_conversation, _pedidos_ativos
from app.agents.tools.tool_definitions import WHATSAPP_AGENT_TOOLS, SALES_AGENT_TOOLS, SAC_AGENT_TOOLS
from app.agents.exceptions import (
    ContextLoadError,
    IntentClassificationError,
    ResponseGenerationError,
    InferenceError,
    ToolExecutionError,
)
from app.services.gemini_inference_service import (
    GeminiInferenceServiceError,
    GeminiInferenceTimeoutError,
    GeminiInferenceRateLimitError,
)
from app.services.vertex_inference_service import (
    VertexInferenceServiceError,
    VertexInferenceTimeoutError,
    VertexInferenceRateLimitError,
)
from app.core.database import SessionLocal
from app.core.config import settings
from app.services.order_service import (
    OrderServiceError,
    build_collection_prompt,
    get_active_order,
    get_next_missing_field,
    order_items_snapshot,
    serialize_order,
    update_customer_field,
)
from app.services.realtime_event_bus import realtime_event_bus
from app.services.tool_event_service import emit_tool_event, generate_trace_id
from app.services.inference_service import get_inference_service_with_fallback

logger = structlog.get_logger()


VALID_INTENTS = {"saudacao", "cardapio", "pedido", "status_pedido", "coleta_dados", "suporte", "outro"}
VALID_FLOW_STAGES = {
    "saudacao",
    "explorando_cardapio",
    "fluxo_comanda",
    "coletando_dados",
    "confirmando_pedido",
    "pedido_finalizado",
}


MENU_QUERY_PLAN_PROMPT = """Analise a mensagem do cliente e responda SOMENTE com um JSON válido no formato:
{{"query":"resumo|listar_categorias|todos|categoria:<nome>|buscar:<termo>|item:<nome>"}}

CATEGORIAS DO CARDÁPIO (use categoria:<nome> para estas):
- PIZZA GRANDE, Carnes, Carnes na brasa, Aves, Peixes, Pastas, Porções, Sopas, Entradas, Acompanhamentos, Saladas, Bebidas, Vinhos, Sobremesas

Regras:
- Use "resumo" quando o cliente pedir o cardápio de forma genérica (ex: "quero ver o cardápio", "me mostra o menu").
- Use "listar_categorias" quando o cliente quiser ver as categorias disponíveis.
- Use "categoria:<nome>" quando o cliente mencionar uma CATEGORIA da lista acima (ex: "pizza", "bebida", "carne").
- Use "item:<nome>" SOMENTE quando o cliente mencionar um item ESPECÍFICO com nome completo (ex: "Pizza Margherita", "Coca-Cola 2L").
- Use "buscar:<termo>" quando for uma busca textual ampla que não se encaixa nas categorias.
- IMPORTANTE: "Pizza", "Bebida", "Carne" são CATEGORIAS, não itens. Use categoria:<nome> para elas.
- IMPORTANTE: Se o cliente disser "quero uma pizza" sem especificar qual, use "categoria:pizza" para mostrar as opções.
- Use "todos" SOMENTE quando o cliente pedir EXPLICITAMENTE para ver o cardápio completo.
- Não escreva nada fora do JSON.

Mensagem: {message}
Histórico: {history}
"""


ORDER_ACTION_PLAN_PROMPT = """Analise a mensagem do cliente e responda SOMENTE com um JSON válido no formato:
{{"action":"adicionar|remover|consultar|limpar|total|finalizar|confirmar|none","item_name":"","quantity":1,"observacao":""}}

Regras:
- Use "adicionar" para incluir item no pedido.
- Use "remover" para retirar item do pedido.
- Use "consultar" para ver a comanda atual.
- Use "limpar" para cancelar ou esvaziar a comanda.
- Use "total" para consultar valor total.
- Use "finalizar" para iniciar fechamento do pedido.
- Use "confirmar" quando o cliente estiver confirmando a comanda pronta.
- Use "none" quando não houver ação de pedido clara.
- Se não houver item, devolva item_name vazio.
- Se a quantidade não estiver clara, devolva 1.
- Não escreva nada fora do JSON.

Mensagem: {message}
Histórico: {history}
Pedido atual: {pedido}
Etapa de coleta: {coleta_etapa}
"""


def _tool_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json_object(raw_text: str) -> dict[str, Any] | None:
    if not raw_text:
        return None

    candidate = raw_text.strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


async def _run_json_prompt(prompt: str, *, max_tokens: int = 180) -> dict[str, Any] | None:
    from app.services.inference_service import get_inference_service_with_fallback

    inference_service = get_inference_service_with_fallback("whatsapp_agent")
    result = await inference_service.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return _extract_json_object(result.get("content", ""))


async def _plan_menu_query(state: AgentState) -> str:
    payload = await _run_json_prompt(
        MENU_QUERY_PLAN_PROMPT.format(
            message=state["current_message"],
            history=state.get("_history_text") or "Sem histórico relevante.",
        )
    )
    query = (payload or {}).get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()
    return "resumo"


async def _plan_order_action(state: AgentState) -> dict[str, Any]:
    payload = await _run_json_prompt(
        ORDER_ACTION_PLAN_PROMPT.format(
            message=state["current_message"],
            history=state.get("_history_text") or "Sem histórico relevante.",
            pedido=json.dumps(state.get("pedido_atual") or [], ensure_ascii=False),
            coleta_etapa=state.get("coleta_etapa") or "nenhuma",
        )
    )

    if not payload:
        return {"action": "none", "item_name": "", "quantity": 1, "observacao": ""}

    action = payload.get("action") if isinstance(payload.get("action"), str) else "none"
    item_name = payload.get("item_name") if isinstance(payload.get("item_name"), str) else ""
    observacao = payload.get("observacao") if isinstance(payload.get("observacao"), str) else ""
    quantity = payload.get("quantity") if isinstance(payload.get("quantity"), int) else 1
    if quantity < 1:
        quantity = 1

    return {
        "action": action.strip().lower(),
        "item_name": item_name.strip(),
        "quantity": quantity,
        "observacao": observacao.strip(),
    }


async def _run_tracked_whatsapp_tool(
    state: AgentState,
    tool_name: str,
    tool_input: Dict[str, Any],
    runner: Callable[[], Any],
    *,
    display_name: str,
) -> tuple[Any, Dict[str, Any]]:
    trace_id = generate_trace_id()
    started_at = _tool_timestamp()
    await emit_tool_event(
        source="whatsapp_agent",
        tool_name=tool_name,
        phase="started",
        instance_name=state.get("instance_name", "default"),
        conversation_id=state.get("conversation_id", "unknown"),
        request_id=state.get("request_id", "unknown"),
        trace_id=trace_id,
        input_payload=tool_input,
        display_name=display_name,
        started_at=started_at,
    )
    try:
        result = runner()
        finished_at = _tool_timestamp()
        await emit_tool_event(
            source="whatsapp_agent",
            tool_name=tool_name,
            phase="completed",
            instance_name=state.get("instance_name", "default"),
            conversation_id=state.get("conversation_id", "unknown"),
            request_id=state.get("request_id", "unknown"),
            trace_id=trace_id,
            input_payload=tool_input,
            output_payload=result,
            display_name=display_name,
            started_at=started_at,
            finished_at=finished_at,
        )
        return result, {
            "name": tool_name,
            "input": tool_input,
            "output": result,
            "status": "completed",
            "trace_id": trace_id,
            "started_at": started_at,
            "finished_at": finished_at,
        }
    except Exception as exc:
        finished_at = _tool_timestamp()
        payload = {"error": str(exc)}
        await emit_tool_event(
            source="whatsapp_agent",
            tool_name=tool_name,
            phase="failed",
            instance_name=state.get("instance_name", "default"),
            conversation_id=state.get("conversation_id", "unknown"),
            request_id=state.get("request_id", "unknown"),
            trace_id=trace_id,
            input_payload=tool_input,
            output_payload=payload,
            error=str(exc),
            display_name=display_name,
            started_at=started_at,
            finished_at=finished_at,
        )
        raise


async def _execute_tool_call(
    state: AgentState,
    tool_name: str,
    tool_arguments: Dict[str, Any],
) -> str:
    """
    Execute a tool call dynamically based on the tool name.
    
    Args:
        state: Current agent state
        tool_name: Name of the tool to execute
        tool_arguments: Arguments for the tool
        
    Returns:
        Tool execution result as string
    """
    logger.info(
        "Executing dynamic tool call",
        tool_name=tool_name,
        arguments=tool_arguments,
        conversation_id=state.get("conversation_id"),
    )
    
    if tool_name == "cardapio_tool":
        from app.agents.tools.cardapio_tool import cardapio_tool
        
        raw_query = tool_arguments.get("query", "resumo")
        query = raw_query if isinstance(raw_query, str) and raw_query.strip() else "resumo"
        result, _ = await _run_tracked_whatsapp_tool(
            state,
            "cardapio_tool",
            {"query": query},
            lambda: cardapio_tool.invoke({"query": query}),
            display_name="Consultar cardápio",
        )
        state["cardapio_context"] = result
        state["flow_stage"] = "explorando_cardapio"
        return result
    
    elif tool_name == "pedido_tool":
        from app.agents.tools.pedido_tool import pedido_tool
        
        # Map Gemini function call format to pedido_tool format
        raw_action = tool_arguments.get("action", "consultar")
        action = raw_action if isinstance(raw_action, str) and raw_action.strip() else "consultar"
        tool_input = {
            "acao": action,
            "item_nome": tool_arguments.get("item_nome", "") if isinstance(tool_arguments.get("item_nome", ""), str) else "",
            "quantidade": tool_arguments.get("quantidade", 1) if isinstance(tool_arguments.get("quantidade", 1), int) else 1,
            "observacao": tool_arguments.get("observacao", "") if isinstance(tool_arguments.get("observacao", ""), str) else "",
        }
        
        result, _ = await _run_tracked_whatsapp_tool(
            state,
            "pedido_tool",
            tool_input,
            lambda: pedido_tool.invoke(tool_input),
            display_name="Gerenciar pedido",
        )

        db = SessionLocal()
        try:
            active_order = get_active_order(db, state["conversation_id"])
            if active_order:
                order_state = _build_order_state_payload(active_order)
                state["pedido_atual"] = order_state["pedido_atual"]
                state["pedido_total"] = order_state["pedido_total"]
                state["cliente_nome"] = order_state["cliente_nome"]
                state["cliente_endereco"] = order_state["cliente_endereco"]
                state["cliente_telefone"] = order_state["cliente_telefone"]
                state["forma_pagamento"] = order_state["forma_pagamento"]
                state["coleta_etapa"] = order_state["coleta_etapa"]
                state["flow_stage"] = order_state["flow_stage"]
            elif action == "confirmar":
                state["pedido_atual"] = None
                state["pedido_total"] = None
                state["coleta_etapa"] = None
                state["flow_stage"] = "pedido_finalizado"
            elif action == "limpar":
                state["pedido_atual"] = None
                state["pedido_total"] = None
                state["coleta_etapa"] = None
                state["flow_stage"] = "saudacao"
        finally:
            db.close()

        state["cardapio_context"] = result
        return result
    
    elif tool_name == "horario_tool":
        # Call actual horario_tool instead of returning mock
        from app.agents.tools.horario_tool import horario_tool
        try:
            result = horario_tool.invoke({})
        except Exception as e:
            logger.warning("Horario tool failed, using fallback", error=str(e))
            # Fallback: still call tool with empty args which returns default
            result = horario_tool.invoke({})
        state["cardapio_context"] = result
        return result
    
    elif tool_name == "delivery_tool":
        from app.agents.tools.delivery_tool import delivery_tool, set_active_conversation
        
        set_active_conversation(state["conversation_id"])
        
        tool_input = {
            "acao": tool_arguments.get("acao", "listar_regioes"),
            "bairro": tool_arguments.get("bairro", "") if isinstance(tool_arguments.get("bairro", ""), str) else "",
            "valor_pedido": tool_arguments.get("valor_pedido", 0) if isinstance(tool_arguments.get("valor_pedido", 0), (int, float)) else 0,
        }
        
        result, _ = await _run_tracked_whatsapp_tool(
            state,
            "delivery_tool",
            tool_input,
            lambda: delivery_tool.invoke(tool_input),
            display_name="Consultar taxa de entrega",
        )
        state["cardapio_context"] = result
        return result
    
    else:
        logger.warning("Unknown tool called", tool_name=tool_name)
        return f"Ferramenta '{tool_name}' não encontrada."


def _is_nemotron_model() -> bool:
    from app.services.inference_service import get_inference_service_with_fallback

    inference_service = get_inference_service_with_fallback("whatsapp_agent")
    runtime_model = (inference_service.model or "").strip().lower()
    return "nemotron" in runtime_model


def _normalize_flow_stage(flow_stage: Any) -> str | None:
    if not isinstance(flow_stage, str):
        return None
    candidate = flow_stage.strip().lower()
    return candidate if candidate in VALID_FLOW_STAGES else None


def _flow_stage_from_order(order: Any) -> str | None:
    if order is None:
        return None

    status = getattr(order, "status", None)
    if status == "collecting_data":
        return "coletando_dados"
    if status == "ready_for_confirmation":
        return "confirmando_pedido"
    if status == "closed":
        return "pedido_finalizado"
    if getattr(order, "items", None):
        return "fluxo_comanda"
    return None


def _flow_stage_from_intent(intent: str | None, current_stage: str | None = None) -> str:
    if current_stage in {"coletando_dados", "confirmando_pedido", "pedido_finalizado"}:
        if intent in {"pedido", "coleta_dados", "status_pedido"}:
            return current_stage

    mapping = {
        "saudacao": "saudacao",
        "cardapio": "explorando_cardapio",
        "pedido": "fluxo_comanda",
        "status_pedido": current_stage or "fluxo_comanda",
        "coleta_dados": "coletando_dados",
        "suporte": current_stage or "saudacao",
        "outro": current_stage or "saudacao",
    }
    return mapping.get(intent or "", current_stage or "saudacao")


def _build_order_state_payload(order: Any) -> dict[str, Any]:
    if order is None:
        return {
            "pedido_atual": None,
            "pedido_total": None,
            "cliente_nome": None,
            "cliente_endereco": None,
            "cliente_telefone": None,
            "forma_pagamento": None,
            "coleta_etapa": None,
            "flow_stage": "saudacao",
        }

    status = getattr(order, "status", None)
    coleta_etapa = None
    if status == "collecting_data":
        coleta_etapa = get_next_missing_field(order)
    elif status == "ready_for_confirmation":
        coleta_etapa = "confirmacao"

    pedido_atual = order_items_snapshot(order) or None
    pedido_total = float(getattr(order, "total_amount", 0) or 0)

    return {
        "pedido_atual": pedido_atual,
        "pedido_total": pedido_total,
        "cliente_nome": getattr(order, "customer_name", None),
        "cliente_endereco": getattr(order, "customer_address", None),
        "cliente_telefone": getattr(order, "customer_phone", None),
        "forma_pagamento": getattr(order, "payment_method", None),
        "coleta_etapa": coleta_etapa,
        "flow_stage": _flow_stage_from_order(order) or "fluxo_comanda",
    }




def _format_whatsapp_response(response: str, cardapio_context: str | None) -> str:
    """
    Formata a resposta para WhatsApp garantindo quebras de linha adequadas.
    Preserva a formatação do cardápio quando presente.
    """
    if not response:
        return response
    
    response = response.strip()
    
    # Se o cardápio foi consultado e tem formatação estruturada
    if cardapio_context and len(cardapio_context) > 50:
        # Se o contexto tem quebras de linha mas a resposta não
        if "\n" in cardapio_context and "\n" not in response:
            # Retornar o contexto diretamente com uma introdução curta se necessário
            if "📋" in cardapio_context or "🍽️" in cardapio_context or "🔍" in cardapio_context:
                return cardapio_context
    
    # Garantir espaçamento adequado antes de listas
    response = re.sub(r'([.!?])\s*([•\-\d])', r'\1\n\n\2', response)
    
    # Garantir espaçamento antes de emojis de seção
    response = re.sub(r'([.!?])\s*([📋🛒💰🍕🔍])', r'\1\n\n\2', response)
    
    return response


def _compact_generation_prompt(
    *,
    current_message: str,
    intent: str,
    flow_stage: str,
    cardapio_context: str,
    pedido_texto: str,
) -> str:
    prompt = (
        "Você é Macedinho da Macedos. "
        "Responda em português brasileiro, em no máximo 2 frases curtas, "
        "sem mostrar raciocínio, sem pedir para esperar, sendo gentil e proativo."
    )

    return (
        f"{prompt} "
        f"Fluxo atual: {flow_stage}. "
        f"Intenção: {intent}. "
        f"Mensagem do cliente: {current_message}. "
        f"Cardápio consultado: {cardapio_context or 'nenhum'}. "
        f"Pedido atual: {pedido_texto or 'vazio'}."
    )


async def validate_message_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 0: Valida se a mensagem deve ser processada.

    Verificações:
    - Mensagem não é do próprio bot
    - Mensagem não está vazia
    - Mensagem não foi processada recentemente (deduplicação)
    - Remote JID é válido

    Se a validação falhar, define should_respond=False para encerrar o fluxo.
    """
    conversation_id = state["conversation_id"]
    current_message = state.get("current_message", "")
    remote_jid = state.get("remote_jid", "")
    correlation_id = state.get("correlation_id") or str(uuid.uuid4())

    logger.info(
        "Validating message",
        correlation_id=correlation_id,
        conversation_id=conversation_id,
        node="validate_message",
        message_length=len(current_message),
        remote_jid=remote_jid
    )

    # Validação 1: Mensagem não pode estar vazia
    if not current_message or not current_message.strip():
        logger.warning(
            "Message validation failed: empty message",
            correlation_id=correlation_id,
            conversation_id=conversation_id
        )
        return {
            "should_respond": False,
            "error": "Empty message",
            "response": None
        }

    # Validação 2: Remote JID deve ser válido (formato WhatsApp)
    if not remote_jid or "@" not in remote_jid:
        logger.warning(
            "Message validation failed: invalid remote JID",
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            remote_jid=remote_jid
        )
        return {
            "should_respond": False,
            "error": "Invalid remote JID",
            "response": None
        }

    # Validação 3: Verificar se é mensagem de grupo (grupos terminam com @g.us)
    # Por enquanto, apenas logar - podemos adicionar lógica específica para grupos depois
    is_group = remote_jid.endswith("@g.us")
    if is_group:
        logger.info(
            "Message from group chat",
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            remote_jid=remote_jid
        )

    # Validação 4: Verificar se mensagem é muito longa (limite WhatsApp: 65536 chars)
    if len(current_message) > 65536:
        logger.warning(
            "Message validation failed: message too long",
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            message_length=len(current_message)
        )
        return {
            "should_respond": False,
            "error": "Message too long",
            "response": None
        }

    logger.info(
        "Message validation passed",
        correlation_id=correlation_id,
        conversation_id=conversation_id,
        node="validate_message"
    )

    return {
        "should_respond": True,
        "correlation_id": correlation_id
    }


async def load_context_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 1: Carrega o contexto da conversa.
    - Histórico de mensagens do DB
    - Pedido atual (carrinho)
    - Informações do cliente coletadas
    - Tipo de agente ativo e roteamento
    """
    conversation_id = state["conversation_id"]
    correlation_id = state.get("correlation_id") or str(uuid.uuid4())

    logger.info(
        "Loading context",
        correlation_id=correlation_id,
        conversation_id=conversation_id,
        node="load_context"
    )

    try:
        # Carregar histórico de mensagens
        history = load_conversation_history(conversation_id, limit=10)

        # Formatar histórico para o LLM
        history_text = ""
        for msg in history:
            role_label = "Cliente" if msg["role"] == "user" else "Macedinho"
            history_text += f"{role_label}: {msg['content']}\n"

        set_active_conversation(conversation_id)
        active_order = None
        conversation_db = None
        db = SessionLocal()
        try:
            # Carregar pedido ativo
            active_order = get_active_order(db, conversation_id)
            order_state = _build_order_state_payload(active_order)
            _pedidos_ativos[conversation_id] = order_state.get("pedido_atual") or []
            
            # Carregar conversa para obter tipo de agente
            from app.models.models import Conversation
            conversation_db = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            # Rotear agente baseado na mensagem atual
            from app.agents.agent_router import route_agent
            routing_result = route_agent(
                conversation_id=conversation_id,
                message=state["current_message"],
                conversation_db=conversation_db
            )
            
            active_agent_type = routing_result["agent_type"]
            
            logger.info(
                "Agent routing completed",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                active_agent_type=active_agent_type,
                transition_occurred=routing_result["transition_occurred"]
            )
            
        except Exception as e:
            db.close()
            raise ContextLoadError(
                f"Failed to load order context: {str(e)}",
                context={
                    "conversation_id": conversation_id,
                    "correlation_id": correlation_id
                }
            ) from e
        finally:
            db.close()

        logger.info(
            "Context loaded successfully",
            correlation_id=correlation_id,
            conversation_id=conversation_id,
            history_length=len(history)
        )

        return {
            "messages": [],
            "_history_text": history_text,
            "active_agent_type": active_agent_type,
            "cardapio_context": None,
            "cardapio_items": None,
            **order_state,
            "response": None,
            "output_type": None,
            "output_data": None,
            "should_respond": True,
            "error": None,
        }

    except ContextLoadError:
        raise
    except Exception as e:
        raise ContextLoadError(
            f"Failed to load conversation context: {str(e)}",
            context={
                "conversation_id": conversation_id,
                "correlation_id": correlation_id
            }
        ) from e


async def classify_intent_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 2: Classifica a intenção da mensagem do cliente.
    Usa o LLM para determinar a intenção.
    """
    from app.services.inference_service import get_inference_service_with_fallback

    current_message = state["current_message"]
    history_text = state.get("_history_text", "")
    current_stage = _normalize_flow_stage(state.get("flow_stage"))
    correlation_id = state.get("correlation_id") or str(uuid.uuid4())

    logger.info(
        "Classifying intent",
        correlation_id=correlation_id,
        conversation_id=state.get("conversation_id"),
        message_preview=current_message[:100],
        node="classify_intent"
    )

    try:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            message=current_message,
            history=history_text or "Sem histórico relevante.",
            flow_stage=current_stage or "nenhum",
            coleta_etapa=state.get("coleta_etapa") or "nenhuma",
            pedido_atual=json.dumps(state.get("pedido_atual") or [], ensure_ascii=False),
        )

        inference_service = get_inference_service_with_fallback("whatsapp_agent")
        result = await inference_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=140,
            temperature=0.1,
        )

        payload = _extract_json_object(result.get("content", "")) or {}
        intent_raw = payload.get("intent")
        normalized_intent = intent_raw.strip().lower() if isinstance(intent_raw, str) else ""
        intent = normalized_intent if normalized_intent in VALID_INTENTS else "outro"
        flow_stage = _normalize_flow_stage(payload.get("flow_stage")) or _flow_stage_from_intent(intent, current_stage)

        logger.info(
            "Intent classified",
            correlation_id=correlation_id,
            intent=intent,
            flow_stage=flow_stage,
            node="classify_intent"
        )

        return {
            "intent": intent,
            "intent_confidence": 0.8,
            "flow_stage": flow_stage,
        }

    except (InferenceError, GeminiInferenceServiceError, GeminiInferenceTimeoutError, GeminiInferenceRateLimitError,
            VertexInferenceServiceError, VertexInferenceTimeoutError, VertexInferenceRateLimitError, Exception) as e:
        inference_errors = (InferenceError, GeminiInferenceServiceError, GeminiInferenceTimeoutError, GeminiInferenceRateLimitError,
                          VertexInferenceServiceError, VertexInferenceTimeoutError, VertexInferenceRateLimitError)
        if isinstance(e, inference_errors):
            # Erro específico de inferência - relançar
            logger.error(
                "Inference error during intent classification",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
                context=getattr(e, 'context', {})
            )
            raise IntentClassificationError(
                f"Failed to classify intent due to inference error: {str(e)}",
                context={
                    "conversation_id": state.get("conversation_id"),
                    "correlation_id": correlation_id,
                    "error_type": type(e).__name__
                }
            ) from e
        else:
            # Outro erro - converter para IntentClassificationError
            logger.error(
                "Error classifying intent",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise IntentClassificationError(
                f"Failed to classify intent: {str(e)}",
                context={
                    "conversation_id": state.get("conversation_id"),
                    "correlation_id": correlation_id
                }
            ) from e


async def execute_action_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 3: Executa a ação baseada na intenção.
    - cardapio: Consulta o cardápio
    - pedido: Gerencia o pedido
    - coleta_dados: Processa dados do cliente
    - Outros: Não executa ação (deixa para o LLM responder)
    """
    from app.agents.tools.cardapio_tool import cardapio_tool

    intent = state["intent"]
    flow_stage = _normalize_flow_stage(state.get("flow_stage")) or _flow_stage_from_intent(intent)
    set_active_conversation(state["conversation_id"])

    logger.info("Executing action", intent=intent)

    cardapio_context = None
    output_type = None
    output_data = None
    tool_calls: list[dict[str, Any]] = []
    pedido_atual = state.get("pedido_atual") or []
    pedido_total = state.get("pedido_total")
    cliente_nome = state.get("cliente_nome")
    cliente_endereco = state.get("cliente_endereco")
    cliente_telefone = state.get("cliente_telefone")
    forma_pagamento = state.get("forma_pagamento")
    coleta_etapa = state.get("coleta_etapa")

    try:
        if intent == "cardapio":
            query = await _plan_menu_query(state)
            cardapio_result, tool_call = await _run_tracked_whatsapp_tool(
                state,
                "cardapio_tool",
                {"query": query},
                lambda: cardapio_tool.invoke({"query": query}),
                display_name="Consultar cardápio",
            )
            cardapio_context = cardapio_result
            tool_calls.append(tool_call)
            flow_stage = "explorando_cardapio"

        elif intent == "pedido":
            from app.agents.tools.pedido_tool import pedido_tool

            order_plan = await _plan_order_action(state)
            if order_plan.get("action") and order_plan.get("action") != "none":
                tool_input = {
                    "acao": order_plan.get("action"),
                    "item_nome": order_plan.get("item_name", ""),
                    "quantidade": order_plan.get("quantity", 1),
                    "observacao": order_plan.get("observacao", ""),
                }
                pedido_result, tool_call = await _run_tracked_whatsapp_tool(
                    state,
                    "pedido_tool",
                    tool_input,
                    lambda: pedido_tool.invoke(tool_input),
                    display_name="Atualizar pedido",
                )
                cardapio_context = pedido_result
                tool_calls.append(tool_call)

                db = SessionLocal()
                try:
                    active_order = get_active_order(db, state["conversation_id"])
                    if active_order:
                        order_state = _build_order_state_payload(active_order)
                        pedido_atual = order_state["pedido_atual"] or []
                        pedido_total = order_state["pedido_total"]
                        cliente_nome = order_state["cliente_nome"]
                        cliente_endereco = order_state["cliente_endereco"]
                        cliente_telefone = order_state["cliente_telefone"]
                        forma_pagamento = order_state["forma_pagamento"]
                        coleta_etapa = order_state["coleta_etapa"]
                        flow_stage = order_state["flow_stage"]
                    elif tool_input["acao"] == "confirmar":
                        pedido_atual = []
                        pedido_total = None
                        coleta_etapa = None
                        flow_stage = "pedido_finalizado"
                    elif tool_input["acao"] == "limpar":
                        pedido_atual = []
                        pedido_total = None
                        coleta_etapa = None
                        flow_stage = "saudacao"
                finally:
                    db.close()
            else:
                flow_stage = _flow_stage_from_intent(intent, flow_stage)

        elif intent == "status_pedido":
            from app.agents.tools.pedido_tool import pedido_tool

            pedido_result, tool_call = await _run_tracked_whatsapp_tool(
                state,
                "pedido_tool",
                {"acao": "consultar"},
                lambda: pedido_tool.invoke({"acao": "consultar"}),
                display_name="Consultar pedido",
            )
            cardapio_context = pedido_result
            output_type = "visualizacao"
            tool_calls.append(tool_call)

            db = SessionLocal()
            try:
                active_order = get_active_order(db, state["conversation_id"])
                if active_order:
                    order_state = _build_order_state_payload(active_order)
                    pedido_atual = order_state["pedido_atual"] or []
                    pedido_total = order_state["pedido_total"]
                    cliente_nome = order_state["cliente_nome"]
                    cliente_endereco = order_state["cliente_endereco"]
                    cliente_telefone = order_state["cliente_telefone"]
                    forma_pagamento = order_state["forma_pagamento"]
                    coleta_etapa = order_state["coleta_etapa"]
                    flow_stage = order_state["flow_stage"]
                else:
                    flow_stage = _flow_stage_from_intent(intent, flow_stage)
            finally:
                db.close()

        elif intent == "coleta_dados":
            output_data = _processar_coleta_dados(state)
            output_type = output_data.get("output_type", "coleta")
            cardapio_context = output_data.get("mensagem_formatada") or output_data.get("mensagem")
            pedido_atual = output_data.get("pedido_atual") or pedido_atual
            pedido_total = output_data.get("pedido_total", pedido_total)
            cliente_nome = output_data.get("cliente_nome", cliente_nome)
            cliente_endereco = output_data.get("cliente_endereco", cliente_endereco)
            cliente_telefone = output_data.get("cliente_telefone", cliente_telefone)
            forma_pagamento = output_data.get("forma_pagamento", forma_pagamento)
            coleta_etapa = output_data.get("coleta_etapa", coleta_etapa)
            flow_stage = output_data.get("flow_stage", flow_stage)

    except Exception as e:
        logger.error("Error executing action", error=str(e))
        return {"error": f"Erro na ação: {str(e)}"}

    return {
        "cardapio_context": cardapio_context,
        "pedido_atual": pedido_atual if pedido_atual else None,
        "pedido_total": pedido_total,
        "cliente_nome": cliente_nome,
        "cliente_endereco": cliente_endereco,
        "cliente_telefone": cliente_telefone,
        "forma_pagamento": forma_pagamento,
        "coleta_etapa": coleta_etapa,
        "flow_stage": flow_stage,
        "output_type": output_type,
        "tool_calls": tool_calls,
        "output_data": output_data,
    }


async def _emit_thinking_event(
    instance_name: str,
    conversation_id: str,
    event: str,
    data: Dict[str, Any] | None = None,
) -> None:
    """Emit a streaming event to the frontend via the realtime event bus."""
    try:
        await realtime_event_bus.publish({
            "instance_name": instance_name,
            "type": "thinking",
            "conversationId": conversation_id,
            "payload": {
                "conversation_id": conversation_id,
                "event": event,
                "data": data or {},
            },
        })
    except Exception as exc:
        logger.warning("Failed to emit thinking event", error=str(exc), event_type=event)


async def _astream_with_optional_tools(
    inference_service: Any,
    *,
    messages: list[dict[str, Any]],
    system_prompt: str | None,
    max_tokens: int,
    temperature: float,
    tools: list[dict[str, Any]] | None,
):
    try:
        # Pass tools to the inference service if available
        async for item in inference_service.astream_chat_completion_with_thinking(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
        ):
            yield item
    except TypeError as exc:
        # Fallback: try without tools if the service doesn't support them
        logger.info(
            "Streaming inference with tools failed; retrying without tools",
            error=str(exc),
        )
        async for item in inference_service.astream_chat_completion_with_thinking(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield item


async def generate_response_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 4: Gera a resposta usando o LLM com streaming de thinking tokens.
    Monta o contexto e gera uma resposta natural.
    """
    current_message = state["current_message"]
    intent = state["intent"]
    cardapio_context = state.get("cardapio_context", "")
    pedido_atual = state.get("pedido_atual", [])
    history_text = state.get("_history_text", "")
    conversation_id = state.get("conversation_id", "unknown")
    instance_name = state.get("instance_name", "default")
    flow_stage = _normalize_flow_stage(state.get("flow_stage")) or _flow_stage_from_intent(intent)
    correlation_id = state.get("correlation_id") or str(uuid.uuid4())

    logger.info(
        "Generating response",
        correlation_id=correlation_id,
        intent=intent,
        conversation_id=conversation_id,
        node="generate_response"
    )

    from app.services.inference_service import get_inference_service_with_fallback

    logger.info(
        "Getting inference service for whatsapp_agent",
        correlation_id=correlation_id,
        conversation_id=conversation_id
    )
    inference_service = get_inference_service_with_fallback("whatsapp_agent")
    logger.info(
        "Inference service obtained",
        correlation_id=correlation_id,
        conversation_id=conversation_id,
        service_class=inference_service.__class__.__name__,
        model=getattr(inference_service, 'model', 'unknown')
    )

    # Montar contexto do pedido
    pedido_texto = ""
    if pedido_atual:
        pedido_texto = "Pedido atual:\n"
        for item in pedido_atual:
            pedido_texto += f"- {item['quantidade']}x {item['nome']} (R$ {item['preco_unitario']:.2f})\n"

    # Montar prompt
    prompt = RESPONSE_GENERATION_PROMPT.format(
        flow_stage=flow_stage,
        cardapio_context=cardapio_context or "Nenhum item consultado ainda.",
        pedido_atual=pedido_texto or "Nenhum item no pedido.",
        cliente_nome=state.get("cliente_nome") or "Não coletado",
        cliente_endereco=state.get("cliente_endereco") or "Não coletado",
        cliente_telefone=state.get("cliente_telefone") or "Não coletado",
        forma_pagamento=state.get("forma_pagamento") or "Não coletado",
        coleta_etapa=state.get("coleta_etapa") or "Nenhuma",
        history=history_text or "Sem histórico anterior.",
        current_message=current_message,
        intent=intent,
    )

    # Emit thinking_start event
    await _emit_thinking_event(
        instance_name=instance_name,
        conversation_id=conversation_id,
        event="thinking_start",
    )

    direct_response: str | None = None
    if isinstance(cardapio_context, str) and cardapio_context.strip():
        if intent in {"cardapio", "status_pedido", "coleta_dados"} or state.get("output_type") in {
            "coleta",
            "comanda",
            "visualizacao",
        }:
            direct_response = _format_whatsapp_response(cardapio_context, cardapio_context)
    elif intent == "saudacao":
        # Só saudar se não houver histórico de conversa
        has_history = bool(history_text and history_text.strip())
        if has_history:
            # Já existe conversa, não saudar novamente
            direct_response = None  # Deixar o LLM gerar resposta apropriada
        else:
            # Primeira mensagem: usar variações de banco (rápido) ou LLM
            # Por performance, usamos variações diretas para saudação inicial
            direct_response = get_saudacao(tem_historico=False)

    if direct_response:
        await _emit_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_end",
            data={"summary": f"Intenção: {intent}"},
        )
        await _emit_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="response_end",
            data={"content": direct_response},
        )
        return {"response": direct_response}

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        system_prompt = None

        if _is_nemotron_model():
            messages = [
                {
                    "role": "user",
                    "content": _compact_generation_prompt(
                        current_message=current_message,
                        intent=intent or "outro",
                        flow_stage=flow_stage,
                        cardapio_context=cardapio_context or "",
                        pedido_texto=pedido_texto or "",
                    ),
                }
            ]

        # Use streaming inference with optional function calling support
        thinking_buffer: list[str] = []
        response_buffer: list[str] = []
        thinking_end_emitted = False
        response_started = False
        tool_round = 0
        max_tool_rounds = 3

        token_count = {"thinking": 0, "response": 0}
        tools_enabled = (
            inference_service.__class__.__name__ == "GeminiInferenceService"
            and not _is_nemotron_model()
            and not bool(state.get("tool_calls"))
            and not bool(state.get("output_data"))
        )

        while True:
            logger.info(
                "Starting streaming inference",
                conversation_id=conversation_id,
                message_count=len(messages),
                tool_round=tool_round,
                tools_enabled=tools_enabled,
                service_class=inference_service.__class__.__name__,
            )

            pending_tool_calls: list[dict[str, Any]] = []

            # Selecionar ferramentas baseadas no tipo de agente ativo
            active_agent_type = state.get("active_agent_type", "sales")
            if active_agent_type == "sales":
                tools_to_use = SALES_AGENT_TOOLS if tools_enabled else None
            elif active_agent_type == "sac":
                tools_to_use = SAC_AGENT_TOOLS if tools_enabled else None
            else:
                tools_to_use = WHATSAPP_AGENT_TOOLS if tools_enabled else None

            async for token_type, token in _astream_with_optional_tools(
                inference_service,
                messages=messages,
                system_prompt=system_prompt,
                max_tokens=settings.AGENT_RESPONSE_MAX_TOKENS,
                temperature=0.2,
                tools=tools_to_use,
            ):
                if token_type == "thinking":
                    text_token = token if isinstance(token, str) else str(token)
                    thinking_buffer.append(text_token)
                    token_count["thinking"] += 1

                    if token_count["thinking"] == 1 or token_count["thinking"] % 10 == 0:
                        logger.debug(
                            "Received thinking tokens",
                            conversation_id=conversation_id,
                            total_thinking_tokens=token_count["thinking"],
                            buffer_length=len("".join(thinking_buffer)),
                        )

                    await _emit_thinking_event(
                        instance_name=instance_name,
                        conversation_id=conversation_id,
                        event="thinking_token",
                        data={"token": text_token},
                    )
                elif token_type == "response":
                    text_token = token if isinstance(token, str) else str(token)
                    if not thinking_end_emitted:
                        interim_thinking = "".join(thinking_buffer).strip()
                        interim_summary = interim_thinking[:120] if interim_thinking else f"Intenção: {intent}"
                        logger.info(
                            "Thinking phase ended",
                            conversation_id=conversation_id,
                            thinking_tokens=token_count["thinking"],
                            thinking_length=len(interim_thinking),
                        )
                        await _emit_thinking_event(
                            instance_name=instance_name,
                            conversation_id=conversation_id,
                            event="thinking_end",
                            data={"summary": interim_summary},
                        )
                        thinking_end_emitted = True

                    if not response_started:
                        logger.info("Response phase started", conversation_id=conversation_id)
                        await _emit_thinking_event(
                            instance_name=instance_name,
                            conversation_id=conversation_id,
                            event="response_start",
                        )
                        response_started = True

                    response_buffer.append(text_token)
                    token_count["response"] += 1

                    if token_count["response"] == 1 or token_count["response"] % 10 == 0:
                        logger.debug(
                            "Received response tokens",
                            conversation_id=conversation_id,
                            total_response_tokens=token_count["response"],
                            buffer_length=len("".join(response_buffer)),
                        )

                    await _emit_thinking_event(
                        instance_name=instance_name,
                        conversation_id=conversation_id,
                        event="response_token",
                        data={"token": text_token},
                    )
                elif token_type == "tool_call":
                    if isinstance(token, dict) and isinstance(token.get("name"), str):
                        tool_name = token["name"].strip()
                        if tool_name:
                            tool_arguments = token.get("arguments", {})
                            pending_tool_calls.append({
                                "name": tool_name,
                                "arguments": tool_arguments if isinstance(tool_arguments, dict) else {},
                            })
                            logger.info(
                                "Received tool call from model",
                                conversation_id=conversation_id,
                                tool_name=tool_name,
                                tool_round=tool_round,
                            )

            if not pending_tool_calls:
                break

            if tool_round >= max_tool_rounds:
                logger.warning(
                    "Maximum tool-calling rounds reached",
                    conversation_id=conversation_id,
                    max_tool_rounds=max_tool_rounds,
                )
                break

            model_parts: list[dict[str, Any]] = []
            function_response_parts: list[dict[str, Any]] = []

            for tool_call in pending_tool_calls:
                tool_name = tool_call["name"]
                tool_arguments = tool_call.get("arguments", {})
                tool_result = await _execute_tool_call(state, tool_name, tool_arguments)
                existing_tool_calls = list(state.get("tool_calls") or [])
                existing_tool_calls.append({
                    "name": tool_name,
                    "input": tool_arguments,
                    "output": tool_result,
                    "status": "completed",
                })
                state["tool_calls"] = existing_tool_calls

                model_parts.append({
                    "functionCall": {
                        "name": tool_name,
                        "args": tool_arguments,
                    }
                })
                function_response_parts.append({
                    "functionResponse": {
                        "name": tool_name,
                        "response": {
                            "result": tool_result,
                        },
                    }
                })

            messages = [
                *messages,
                {"role": "model", "parts": model_parts},
                {"role": "user", "parts": function_response_parts},
            ]
            cardapio_context = state.get("cardapio_context", cardapio_context)
            pedido_atual = state.get("pedido_atual") or []
            flow_stage = _normalize_flow_stage(state.get("flow_stage")) or flow_stage
            tool_round += 1

        # Create summary from thinking content (first 120 chars)
        thinking_content = "".join(thinking_buffer)
        summary = thinking_content[:120] if thinking_content else f"Intenção: {intent}"

        # Join response tokens into final response
        response = "".join(response_buffer).strip()

        # Log streaming summary
        logger.info(
            "Streaming completed",
            conversation_id=conversation_id,
            thinking_tokens=token_count["thinking"],
            response_tokens=token_count["response"],
            thinking_length=len(thinking_content),
            response_length=len(response),
            has_response=bool(response),
            thinking_preview=thinking_content[:100] if thinking_content else "(empty)",
            response_preview=response[:100] if response else "(empty)",
        )

        # Limpar tags de thinking do Qwen (just in case)
        think_tag = "</think>"
        if think_tag in response:
            response = response.split(think_tag)[-1].strip()

        # Aplicar formatação para WhatsApp
        response = _format_whatsapp_response(response, cardapio_context)

        if not response:
            logger.warning(
                "Model produced empty response; attempting fallback strategies",
                conversation_id=conversation_id,
                thinking_length=len(thinking_content),
                has_thinking=bool(thinking_content),
            )
            
            # Strategy 1: Use thinking content as response if it already looks user-facing
            thinking_lower = thinking_content.lower()
            looks_like_internal_reasoning = any(
                marker in thinking_lower
                for marker in ["fluxo", "regra", "cliente quer", "vamos seguir", "de acordo com"]
            )

            if thinking_content and not looks_like_internal_reasoning:
                logger.info(
                    "Using thinking content as response",
                    conversation_id=conversation_id,
                    thinking_length=len(thinking_content),
                )
                response = thinking_content.strip()
            else:
                # Verificar se há histórico para decidir se deve saudar
                has_history = bool(history_text and history_text.strip())
                
                if intent == "saudacao":
                    # Usar variações de banco para resposta rápida
                    response = get_saudacao(tem_historico=has_history)
                elif intent == "outro":
                    # Usar variações de banco para resposta rápida
                    response = get_fallback_message(tem_historico=has_history)
                else:
                    logger.info(
                        "Generating fallback response via LLM",
                        conversation_id=conversation_id,
                    )
                    # Instrução para não saudar se já houver histórico
                    no_greet_instruction = "" if has_history else "Inclua uma saudação inicial."
                    fallback_prompt = (
                        f"Você é Macedinho da Macedos. O cliente disse: '{current_message}'. "
                        f"Responda de forma gentil e proativa em 1-2 frases curtas. "
                        f"{'NÃO saudar, apenas responda ao assunto diretamente. ' if has_history else ''}"
                        f"{no_greet_instruction} "
                        f"Fluxo atual: {flow_stage}. Intenção: {intent}."
                    )
                    fallback_result = await inference_service.chat_completion(
                        messages=[{"role": "user", "content": fallback_prompt}],
                        max_tokens=100,
                        temperature=0.3,
                    )
                    response = fallback_result.get("content", "").strip() or get_fallback_message(tem_historico=has_history)
                    logger.info(
                        "Fallback response generated",
                        conversation_id=conversation_id,
                        response_length=len(response),
                    )

        if not thinking_end_emitted:
            await _emit_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="thinking_end",
                data={"summary": summary},
            )

        if response_started:
            await _emit_thinking_event(
                instance_name=instance_name,
                conversation_id=conversation_id,
                event="response_end",
                data={"content": response},
            )

        logger.info(
            "Response generated successfully",
            conversation_id=conversation_id,
            response_length=len(response),
            thinking_length=len(thinking_content),
        )

        return {"response": response}

    except (InferenceError, GeminiInferenceServiceError, GeminiInferenceTimeoutError, GeminiInferenceRateLimitError,
            VertexInferenceServiceError, VertexInferenceTimeoutError, VertexInferenceRateLimitError, Exception) as e:
        import traceback
        error_traceback = traceback.format_exc()

        inference_errors = (InferenceError, GeminiInferenceServiceError, GeminiInferenceTimeoutError, GeminiInferenceRateLimitError,
                          VertexInferenceServiceError, VertexInferenceTimeoutError, VertexInferenceRateLimitError)
        if isinstance(e, inference_errors):
            # Erro específico de inferência - relançar como ResponseGenerationError
            logger.error(
                "Inference error during response generation",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                error=str(e),
                error_type=type(e).__name__,
                context=getattr(e, 'context', {}),
                traceback=error_traceback
            )
            raise ResponseGenerationError(
                f"Failed to generate response due to inference error: {str(e)}",
                context={
                    "conversation_id": conversation_id,
                    "correlation_id": correlation_id,
                    "intent": intent,
                    "error_type": type(e).__name__
                }
            ) from e
        else:
            # Outro erro - converter para ResponseGenerationError
            logger.error(
                "Error generating response",
                correlation_id=correlation_id,
                conversation_id=conversation_id,
                error=str(e),
                error_type=type(e).__name__,
                traceback=error_traceback
            )
            raise ResponseGenerationError(
                f"Failed to generate response: {str(e)}",
                context={
                    "conversation_id": conversation_id,
                    "correlation_id": correlation_id,
                    "intent": intent
                }
            ) from e


def _processar_coleta_dados(state: AgentState) -> Dict[str, Any]:
    """Processa os dados coletados do cliente."""
    message = state["current_message"].strip()
    coleta_etapa = state.get("coleta_etapa")
    db = SessionLocal()

    try:
        if not coleta_etapa:
            active_order = get_active_order(db, state["conversation_id"])
            if not active_order:
                mensagem_sem_comanda = get_mensagem_sem_comanda()
                return {
                    "output_type": "mensagem",
                    "mensagem": mensagem_sem_comanda,
                    "mensagem_formatada": mensagem_sem_comanda,
                    "pedido_atual": [],
                    "pedido_total": None,
                    "flow_stage": "saudacao",
                }
            coleta_etapa = get_next_missing_field(active_order)

        order = update_customer_field(db, state["conversation_id"], coleta_etapa or "", message)
        order_state = _build_order_state_payload(order)
        pedido_atual = order_state["pedido_atual"] or []
        pedido_total = order_state["pedido_total"]

        if order.status == "ready_for_confirmation":
            comanda = format_comanda(serialize_order(order))
            mensagem = f"{comanda}\n\nSe estiver tudo certo, responda *CONFIRMAR*."
            return {
                **order_state,
                "output_type": "comanda",
                "mensagem": mensagem,
                "mensagem_formatada": mensagem,
                "pedido_atual": pedido_atual,
                "pedido_total": pedido_total,
                "dados_coletados": build_collection_prompt(order).get("dados_coletados", {}),
                "proxima_etapa": "confirmacao",
                "coleta_etapa": "confirmacao",
                "flow_stage": "confirmando_pedido",
            }

        coleta_payload = build_collection_prompt(order)
        return {
            **order_state,
            **coleta_payload,
            "output_type": "coleta",
            "mensagem_formatada": format_coleta(coleta_payload),
            "pedido_atual": pedido_atual,
            "pedido_total": pedido_total,
            "flow_stage": "coletando_dados",
        }
    except OrderServiceError as exc:
        return {
            "output_type": "mensagem",
            "mensagem": str(exc),
            "mensagem_formatada": str(exc),
            "pedido_atual": state.get("pedido_atual") or [],
            "pedido_total": state.get("pedido_total"),
            "cliente_nome": state.get("cliente_nome"),
            "cliente_endereco": state.get("cliente_endereco"),
            "cliente_telefone": state.get("cliente_telefone"),
            "forma_pagamento": state.get("forma_pagamento"),
            "coleta_etapa": state.get("coleta_etapa"),
            "flow_stage": state.get("flow_stage") or "coletando_dados",
        }
    finally:
        db.close()
