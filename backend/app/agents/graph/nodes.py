"""
Graph Nodes - Nós do grafo LangGraph para o agente WhatsApp.
Cada nó é uma etapa do processamento da mensagem.
"""
import re
from typing import Dict, Any
import structlog

from app.agents.state import AgentState
from app.agents.prompts import INTENT_CLASSIFICATION_PROMPT, RESPONSE_GENERATION_PROMPT, SYSTEM_PROMPT
from app.agents.memory.history_loader import load_conversation_history
from app.agents.tools.pedido_tool import set_active_conversation, _pedidos_ativos
from app.core.config import settings
from app.services.menu_catalog_service import find_matching_category_name
from app.services.realtime_event_bus import realtime_event_bus

logger = structlog.get_logger()


def _is_nemotron_model() -> bool:
    """Check whether the active LM Studio model is the Nemotron variant."""
    return "nemotron" in settings.LM_STUDIO_MODEL.lower()


def _direct_greeting_response() -> str:
    """Return a deterministic greeting for short salutations."""
    return "😊 Olá! Posso te mostrar o cardápio ou montar seu pedido."


def _generic_direct_response() -> str:
    """Return a deterministic fallback when the model does not emit final text."""
    return "😊 Posso te ajudar com o cardápio, seu pedido ou o status do pedido."


def _compact_generation_prompt(
    *,
    current_message: str,
    intent: str,
    cardapio_context: str,
    pedido_texto: str,
) -> str:
    """Build a compact prompt for models that struggle with long system prompts."""
    prompt = (
        "Você é Macedinho da Macedos. "
        "Responda em português brasileiro, em no máximo 2 frases curtas, "
        "sem mostrar raciocínio e sem pedir para esperar."
    )

    if intent == "pedido":
        return (
            f"{prompt} "
            f"Mensagem do cliente: {current_message}. "
            f"Estado atual do pedido: {pedido_texto or 'vazio'}."
        )

    if intent == "status_pedido":
        return (
            f"{prompt} "
            f"Cliente pediu o status do pedido. "
            f"Contexto do pedido: {cardapio_context or pedido_texto or 'pedido vazio'}."
        )

    return f"{prompt} Mensagem do cliente: {current_message}."


def _normalize_item_name(item_name: str) -> str:
    """Normalize parsed item text from a free-form order request."""
    normalized = re.sub(r"\s+", " ", item_name).strip(" ,.:;!?-")
    return normalized


def _extract_order_item_and_quantity(message: str) -> tuple[str, int]:
    """Extract the requested item name and quantity from a natural language message."""
    lowered = message.lower().strip()
    cleaned = lowered.replace("quero pedir", "", 1)
    cleaned = re.sub(r"^(?:quero adicionar|adiciona(?:r)?|me vê|me ve|manda|pedir)\s+", "", cleaned)
    cleaned = cleaned.strip()

    quantity = 1
    number_match = re.match(r"^(?P<qty>\d+)\s*x?\s+(?P<item>.+)$", cleaned)
    if number_match:
        quantity = int(number_match.group("qty"))
        return _normalize_item_name(number_match.group("item")), quantity

    article_match = re.match(r"^(?P<article>um|uma|uns|umas)\s+(?P<item>.+)$", cleaned)
    if article_match:
        return _normalize_item_name(article_match.group("item")), 1

    return _normalize_item_name(cleaned), quantity


def _extract_order_item_after_keyword(message: str, keywords: tuple[str, ...]) -> str:
    """Extract an item name after a remove-like keyword."""
    lowered = message.lower().strip()
    for keyword in keywords:
        if keyword in lowered:
            tail = lowered.split(keyword, 1)[1]
            return _normalize_item_name(tail)
    return ""


def _processar_pedido_direto(message: str) -> str | None:
    """Handle simple order operations without delegating to the model."""
    from app.agents.tools.pedido_tool import pedido_tool

    lowered = message.lower()

    if any(term in lowered for term in ["limpar pedido", "cancelar pedido", "esvaziar pedido"]):
        return pedido_tool.invoke({"acao": "limpar"})

    if any(term in lowered for term in ["total", "valor total", "quanto deu"]):
        return pedido_tool.invoke({"acao": "total"})

    if any(term in lowered for term in ["ver pedido", "pedido atual", "meu pedido", "mostrar pedido"]):
        return pedido_tool.invoke({"acao": "consultar"})

    if any(term in lowered for term in ["remove", "remover", "tirar", "excluir"]):
        item_nome = _extract_order_item_after_keyword(message, ("remove", "remover", "tirar", "excluir"))
        if item_nome:
            return pedido_tool.invoke({"acao": "remover", "item_nome": item_nome})
        return "Me diga qual item eu removo do seu pedido."

    if any(term in lowered for term in ["adiciona", "adicionar", "quero pedir", "pedir", "quero adicionar"]):
        item_nome, quantidade = _extract_order_item_and_quantity(message)
        if item_nome:
            return pedido_tool.invoke(
                {
                    "acao": "adicionar",
                    "item_nome": item_nome,
                    "quantidade": quantidade,
                }
            )
        return "Me diga qual item e a quantidade que eu adiciono ao pedido."

    return None


def _infer_intent_from_keywords(message: str) -> str | None:
    """Infer intent from common WhatsApp phrases before calling the model."""
    lowered = message.lower().strip()

    if lowered in {"oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"}:
        return "saudacao"

    if any(term in lowered for term in ["status", "meu pedido", "pedido atual", "andamento do pedido", "como está meu pedido"]):
        return "status_pedido"

    if any(term in lowered for term in ["adiciona", "adicionar", "quero pedir", "pedir", "quero adicionar", "remove", "remover", "tirar", "excluir", "limpar pedido", "cancelar pedido", "valor total", "quanto deu"]):
        return "pedido"

    if any(term in lowered for term in ["cardápio", "cardapio", "menu", "categoria", "categorias"]) or find_matching_category_name(message):
        return "cardapio"

    return None


async def load_context_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 1: Carrega o contexto da conversa.
    - Histórico de mensagens do DB
    - Pedido atual (carrinho)
    - Informações do cliente coletadas
    """
    conversation_id = state["conversation_id"]

    logger.info("Loading context", conversation_id=conversation_id)

    # Carregar histórico de mensagens
    history = load_conversation_history(conversation_id, limit=10)

    # Formatar histórico para o LLM
    history_text = ""
    for msg in history:
        role_label = "Cliente" if msg["role"] == "user" else "Macedinho"
        history_text += f"{role_label}: {msg['content']}\n"

    # Carregar pedido atual do carrinho em memória
    set_active_conversation(conversation_id)
    pedido_atual = _pedidos_ativos.get(conversation_id, [])

    return {
        "messages": [],
        "cardapio_context": None,
        "cardapio_items": None,
        "pedido_atual": pedido_atual if pedido_atual else None,
        "pedido_total": sum(item.get("preco_unitario", 0) * item.get("quantidade", 1) for item in pedido_atual) if pedido_atual else None,
        "cliente_nome": None,
        "cliente_endereco": None,
        "cliente_telefone": None,
        "forma_pagamento": None,
        "coleta_etapa": None,
        "response": None,
        "output_type": None,
        "output_data": None,
        "should_respond": True,
        "error": None,
    }


async def classify_intent_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 2: Classifica a intenção da mensagem do cliente.
    Usa o LLM para determinar a intenção.
    """
    from app.services.inference_service import inference_service

    current_message = state["current_message"]
    history_text = state.get("_history_text", "")

    logger.info("Classifying intent", message=current_message[:100])

    try:
        heuristic_intent = _infer_intent_from_keywords(current_message)
        if heuristic_intent:
            logger.info("Intent classified via heuristic", intent=heuristic_intent)
            return {
                "intent": heuristic_intent,
                "intent_confidence": 0.95,
            }

        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            message=current_message,
            history=history_text
        )

        result = await inference_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.1,
        )

        intent_raw = result.get("content", "outro").strip().lower()

        # Normalizar intenção
        valid_intents = ["saudacao", "cardapio", "pedido", "status_pedido", "coleta_dados", "suporte", "outro"]
        intent = "outro"
        for vi in valid_intents:
            if vi in intent_raw:
                intent = vi
                break

        logger.info("Intent classified", intent=intent)

        return {
            "intent": intent,
            "intent_confidence": 0.8,
        }

    except Exception as e:
        logger.error("Error classifying intent", error=str(e))
        return {
            "intent": "outro",
            "intent_confidence": 0.0,
            "error": f"Erro na classificação: {str(e)}",
        }


async def execute_action_node(state: AgentState) -> Dict[str, Any]:
    """
    Nó 3: Executa a ação baseada na intenção.
    - cardapio: Consulta o cardápio
    - pedido: Gerencia o pedido
    - coleta_dados: Processa dados do cliente
    - Outros: Não executa ação (deixa para o LLM responder)
    """
    from app.agents.tools.cardapio_tool import cardapio_tool
    from app.agents.tools.horario_tool import horario_tool

    intent = state["intent"]
    current_message = state["current_message"]

    logger.info("Executing action", intent=intent)

    cardapio_context = None
    output_type = None
    output_data = None

    try:
        if intent == "cardapio":
            # Consultar cardápio baseado na mensagem
            query = _extrair_query_cardapio(current_message)
            cardapio_result = cardapio_tool.invoke({"query": query})
            cardapio_context = cardapio_result

        elif intent == "pedido":
            pedido_result = _processar_pedido_direto(current_message)
            if pedido_result:
                cardapio_context = pedido_result

        elif intent == "status_pedido":
            # Consultar pedido atual
            from app.agents.tools.pedido_tool import pedido_tool
            pedido_result = pedido_tool.invoke({"acao": "consultar"})
            cardapio_context = pedido_result
            output_type = "visualizacao"

        elif intent == "coleta_dados":
            # Processar dados coletados
            output_type = "coleta"
            output_data = _processar_coleta_dados(state)

    except Exception as e:
        logger.error("Error executing action", error=str(e))
        return {"error": f"Erro na ação: {str(e)}"}

    return {
        "cardapio_context": cardapio_context,
        "output_type": output_type,
        "output_data": output_data,
    }


async def _emit_thinking_event(
    instance_name: str,
    conversation_id: str,
    event: str,
    data: Dict[str, Any] = None,
) -> None:
    """Emit a thinking event to the frontend via the realtime event bus."""
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
        logger.warning("Failed to emit thinking event", error=str(exc), event=event)


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

    logger.info("Generating response", intent=intent, conversation_id=conversation_id)

    # Para cardápio, a tool já devolve a resposta pronta e confiável.
    if intent == "cardapio" and cardapio_context:
        logger.info("Returning direct menu response", length=len(cardapio_context))
        return {"response": cardapio_context}

    if intent == "saudacao":
        response = _direct_greeting_response()
        logger.info("Returning direct greeting response", length=len(response))
        return {"response": response}

    if intent in {"pedido", "status_pedido"} and cardapio_context:
        logger.info("Returning direct order response", length=len(cardapio_context), intent=intent)
        return {"response": cardapio_context}

    if intent == "coleta_dados":
        output_data = state.get("output_data") or {}
        response = output_data.get("mensagem") or "Obrigado pelas informações!"
        logger.info("Returning direct data-collection response", length=len(response))
        return {"response": response}

    from app.services.inference_service import inference_service

    # Montar contexto do pedido
    pedido_texto = ""
    if pedido_atual:
        pedido_texto = "Pedido atual:\n"
        for item in pedido_atual:
            pedido_texto += f"- {item['quantidade']}x {item['nome']} (R$ {item['preco_unitario']:.2f})\n"

    # Montar prompt
    prompt = RESPONSE_GENERATION_PROMPT.format(
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
                        cardapio_context=cardapio_context or "",
                        pedido_texto=pedido_texto or "",
                    ),
                }
            ]

        # Use streaming inference with thinking detection
        thinking_buffer = []
        response_buffer = []

        async for token_type, token in inference_service.astream_chat_completion_with_thinking(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=settings.AGENT_RESPONSE_MAX_TOKENS,
            temperature=0.2,
        ):
            if token_type == "thinking":
                thinking_buffer.append(token)
                # Publish thinking_token event
                await _emit_thinking_event(
                    instance_name=instance_name,
                    conversation_id=conversation_id,
                    event="thinking_token",
                    data={"token": token},
                )
            elif token_type == "response":
                response_buffer.append(token)

        # Join response tokens into final response
        response = "".join(response_buffer).strip()

        # Limpar tags de thinking do Qwen (just in case)
        think_tag = "</" + "think>"
        if think_tag in response:
            response = response.split(think_tag)[-1].strip()

        if not response:
            response = _generic_direct_response()

        # Create summary from thinking content (first 120 chars)
        thinking_content = "".join(thinking_buffer)
        summary = thinking_content[:120] if thinking_content else f"Intenção: {intent}"

        # Emit thinking_end event with summary
        await _emit_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_end",
            data={"summary": summary},
        )

        logger.info("Response generated", length=len(response), thinking_length=len(thinking_content))

        return {"response": response}

    except Exception as e:
        logger.error("Error generating response", error=str(e), conversation_id=conversation_id)

        # Emit thinking_end with error summary
        await _emit_thinking_event(
            instance_name=instance_name,
            conversation_id=conversation_id,
            event="thinking_end",
            data={"summary": "Erro ao gerar resposta"},
        )

        return {
            "response": "Desculpe, estou com dificuldades técnicas no momento. Por favor, tente novamente em instantes. 😊",
            "error": f"Erro na geração: {str(e)}",
        }


def _extrair_query_cardapio(message: str) -> str:
    """Extrai a query de busca do cardápio da mensagem do cliente."""
    msg_lower = message.lower()

    if any(word in msg_lower for word in ["categoria", "categorias", "seções", "tipos"]):
        return "listar_categorias"

    matched_category = find_matching_category_name(message)
    if matched_category:
        return f"categoria:{matched_category}"

    if any(word in msg_lower for word in ["cardápio", "cardapio", "menu", "tudo", "todos", "completo"]):
        return "todos"

    # Busca genérica
    return f"buscar:{message}"


def _processar_coleta_dados(state: AgentState) -> Dict[str, Any]:
    """Processa os dados coletados do cliente."""
    message = state["current_message"].strip()
    coleta_etapa = state.get("coleta_etapa")

    dados = {}

    if coleta_etapa == "nome":
        dados["nome"] = message
    elif coleta_etapa == "endereco":
        dados["endereco"] = message
    elif coleta_etapa == "telefone":
        dados["telefone"] = message
    elif coleta_etapa == "pagamento":
        dados["pagamento"] = message

    return {
        "etapa": coleta_etapa or "inicio",
        "mensagem": "Obrigado pelas informações!",
        "dados_coletados": dados,
        "proxima_etapa": _proxima_etapa_coleta(coleta_etapa),
    }


def _proxima_etapa_coleta(etapa_atual: str) -> str:
    """Determina a próxima etapa da coleta."""
    etapas = ["nome", "endereco", "telefone", "pagamento", "confirmacao"]
    if etapa_atual in etapas:
        idx = etapas.index(etapa_atual)
        if idx < len(etapas) - 1:
            return etapas[idx + 1]
    return "confirmacao"
