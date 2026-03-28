"""
Pedido Tool - Gerenciamento de pedidos do cliente.
Usa a comanda persistida no banco como fonte oficial.
"""
from typing import Any, Dict, List

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.tools import tool

from app.agents.outputs.coleta_output import format_coleta
from app.agents.outputs.finalizacao_output import format_finalizacao
from app.agents.outputs.pedido_output import format_comanda
from app.core.database import SessionLocal
from app.services.order_service import (
    OrderServiceError,
    add_item_to_order,
    begin_checkout,
    build_collection_prompt,
    cancel_active_order,
    confirm_order,
    get_active_order,
    order_items_snapshot,
    remove_item_from_order,
    serialize_order,
)


@tool
def pedido_tool(
    acao: str,
    item_nome: str = "",
    quantidade: int = 1,
    observacao: str = "",
    campo_dado: str = "",
    valor_dado: str = "",
) -> str:
    """
    Gerencia o fluxo de pedido/comanda do cliente.

    Ações:
    - adicionar
    - remover
    - consultar
    - limpar
    - total
    - finalizar
    - confirmar
    """
    db = SessionLocal()
    try:
        acao_lower = acao.lower().strip()

        if acao_lower == "adicionar":
            return _adicionar_item(db, item_nome, quantidade, observacao)
        if acao_lower == "remover":
            return _remover_item(db, item_nome)
        if acao_lower == "consultar":
            return _consultar_pedido(db)
        if acao_lower == "limpar":
            return _limpar_pedido(db)
        if acao_lower == "total":
            return _mostrar_total(db)
        if acao_lower == "finalizar":
            return _iniciar_finalizacao(db)
        if acao_lower == "confirmar":
            return _confirmar_pedido(db)

        return "Ação inválida. Use: adicionar, remover, consultar, limpar, total, finalizar ou confirmar."
    finally:
        db.close()


# Cache legado mantido como espelho do estado persistido para compatibilidade.
_pedidos_ativos: Dict[str, List[Dict[str, Any]]] = {}


def set_pedido_context(conversation_id: str):
    if conversation_id not in _pedidos_ativos:
        _pedidos_ativos[conversation_id] = []


def get_pedido_atual(conversation_id: str) -> List[Dict[str, Any]]:
    pedido_em_cache = _pedidos_ativos.get(conversation_id)
    if pedido_em_cache is not None:
        return pedido_em_cache

    db = SessionLocal()
    try:
        order = get_active_order(db, conversation_id)
        snapshot = order_items_snapshot(order)
        _pedidos_ativos[conversation_id] = snapshot
        return snapshot
    finally:
        db.close()


def set_conversation_id(conversation_id: str):
    set_pedido_context(conversation_id)


_current_conversation_id: str = "default"


def set_active_conversation(conversation_id: str):
    global _current_conversation_id
    _current_conversation_id = conversation_id
    if conversation_id not in _pedidos_ativos:
        _pedidos_ativos[conversation_id] = []


def _sync_cache(conversation_id: str, order) -> None:
    _pedidos_ativos[conversation_id] = order_items_snapshot(order)


def _formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _adicionar_item(db, item_nome: str, quantidade: int, observacao: str) -> str:
    if not item_nome:
        return "Por favor, informe o nome do item que deseja adicionar."

    try:
        order = add_item_to_order(
            db=db,
            conversation_id=_current_conversation_id,
            item_name=item_nome,
            quantity=quantidade,
            notes=observacao,
        )
    except OrderServiceError as exc:
        return str(exc)

    _sync_cache(_current_conversation_id, order)
    added_item = next((item for item in order.items if item.item_name.lower() == item_nome.lower()), None)
    matched_item = added_item or order.items[-1]
    subtotal = float(matched_item.subtotal_price or 0)

    resultado = f"✅ *{matched_item.item_name}* na comanda #{order.order_number}\n"
    resultado += f"📦 {matched_item.quantity}x {_formatar_preco(float(matched_item.unit_price or 0))} = {_formatar_preco(subtotal)}\n"
    if observacao:
        resultado += f"📝 Obs: {observacao}\n"
    resultado += f"\n💰 Parcial: {_formatar_preco(float(order.total_amount or 0))}"
    return resultado


def _remover_item(db, item_nome: str) -> str:
    if not item_nome:
        return "Por favor, informe o nome do item que deseja remover."

    try:
        order = remove_item_from_order(db, _current_conversation_id, item_nome)
    except OrderServiceError as exc:
        return str(exc)

    _sync_cache(_current_conversation_id, order if order.items else None)

    if not order.items:
        return f"❌ Item removido. A comanda #{order.order_number} ficou vazia."

    return f"❌ Item removido.\n💰 Total atualizado: {_formatar_preco(float(order.total_amount or 0))}"


def _consultar_pedido(db) -> str:
    order = get_active_order(db, _current_conversation_id)
    if not order:
        _sync_cache(_current_conversation_id, None)
        return "🛒 Seu pedido está vazio. Quer ver o cardápio para escolher algo?"

    _sync_cache(_current_conversation_id, order)
    resultado = format_comanda(serialize_order(order))
    return f"{resultado}\n\nSe quiser fechar, diga *finalizar pedido*."


def _limpar_pedido(db) -> str:
    order = cancel_active_order(db, _current_conversation_id)
    _sync_cache(_current_conversation_id, None)
    if not order:
        return "🛒 Não há comanda aberta para cancelar."
    return f"🗑️ Comanda #{order.order_number} cancelada. Se quiser, posso abrir uma nova comanda com outro pedido."


def _mostrar_total(db) -> str:
    order = get_active_order(db, _current_conversation_id)
    if not order:
        return "Seu pedido está vazio."
    _sync_cache(_current_conversation_id, order)
    qtd_itens = sum(item.quantity for item in order.items)
    return f"💰 Total da comanda #{order.order_number}: {_formatar_preco(float(order.total_amount or 0))} ({qtd_itens} itens)"


def _iniciar_finalizacao(db) -> str:
    try:
        order = begin_checkout(db, _current_conversation_id)
    except OrderServiceError as exc:
        return str(exc)

    _sync_cache(_current_conversation_id, order)
    if order.status == "collecting_data":
        return format_coleta(build_collection_prompt(order))

    comanda = format_comanda(serialize_order(order))
    return f"{comanda}\n\nSe estiver tudo certo, responda *CONFIRMAR*."


def _confirmar_pedido(db) -> str:
    try:
        order = confirm_order(db, _current_conversation_id)
    except OrderServiceError as exc:
        return str(exc)

    _sync_cache(_current_conversation_id, None)
    return format_finalizacao(
        {
            **serialize_order(order),
            "mensagem_confirmacao": "Sua comanda foi fechada com sucesso.",
        }
    )
