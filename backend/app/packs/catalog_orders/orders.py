"""`gerenciar_pedido` e `status_pedido`: o Order do Contact dentro da Conversation.

Todo acesso é escopado: itens e zonas pela `ctx.company_id`, Order pela `ctx.conversation_id`,
histórico pelo `ctx.contact_id`. Nenhuma ação grava dado parcial: validou e falhou, nada muda.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.models.models import (
    Company,
    Contact,
    CustomerOrder,
    CustomerOrderItem,
    DeliveryZone,
    MenuCatalog,
    MenuItem,
)
from app.packs.catalog_orders import pix
from app.packs.catalog_orders.catalog import normalize, words

ACTIONS = ["adicionar_item", "remover_item", "ver", "definir_dados", "finalizar"]
DELIVERY_TYPES = ["entrega", "retirada"]
PAYMENT_METHODS = ["pix", "dinheiro", "cartao"]
ACTIVE_STATUSES = ("open", "collecting_data", "ready_for_confirmation")

MIN_ADDRESS_LENGTH = 8
# Respostas de checkout que o modelo às vezes grava como se fossem o nome do cliente.
NOT_A_NAME = frozenset(
    "retirada retirar entrega entregar delivery pix dinheiro cartao credito debito sim nao ok confirmar "
    "confirmo finalizar cancelar".split()
)
STATUS_LABELS = {
    "open": "em montagem",
    "collecting_data": "em montagem",
    "ready_for_confirmation": "em montagem",
    "closed": "recebido, aguardando preparo",
    "in_production": "em preparo",
    "sent": "saiu para entrega",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


class OrderError(Exception):
    """Pedido recusado; a mensagem volta ao modelo como `erro`."""


def _ok(data: dict[str, Any]) -> ToolResult:
    return ToolResult(content=json.dumps(data, ensure_ascii=False))


def _error(message: str) -> ToolResult:
    return ToolResult(content=json.dumps({"erro": message}, ensure_ascii=False), is_error=True)


def brl(value: Decimal | float) -> str:
    return f"R$ {Decimal(str(value)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cents(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


# ---------- validação ----------


def validate_name(raw: Any) -> str:
    name = " ".join(str(raw or "").split())
    letters = sum(1 for c in name if c.isalpha())
    if letters < 2 or len(name) > 200:
        raise OrderError("Nome inválido: preciso do nome do cliente (pelo menos 2 letras).")
    if set(words(name)) <= NOT_A_NAME:
        raise OrderError(f"'{name}' não é um nome. Pergunte o nome do cliente.")
    return name


def validate_address(raw: Any) -> str:
    address = " ".join(str(raw or "").split())
    letters = sum(1 for c in address if c.isalpha())
    if len(address) < MIN_ADDRESS_LENGTH or letters < 3 or not re.search(r"\d", address):
        raise OrderError("Endereço inválido: preciso de rua, número e bairro (ex: 'Rua das Flores 123, Centro').")
    return address


def _choice(raw: Any, allowed: list[str], field: str) -> str:
    value = normalize(str(raw or "")).strip()
    if value not in allowed:
        raise OrderError(f"{field} inválido: use {' ou '.join(allowed)}.")
    return value


def _positive_int(raw: Any, field: str, default: int | None) -> int | None:
    if raw is None:
        return default
    try:
        if isinstance(raw, bool) or int(raw) != float(raw):
            raise ValueError
        value = int(raw)
    except (TypeError, ValueError):
        raise OrderError(f"{field} deve ser um número inteiro maior que zero.") from None
    if value < 1:
        raise OrderError(f"{field} deve ser um número inteiro maior que zero.")
    return value


# ---------- zonas ----------


def _neighborhood_names(zone: DeliveryZone) -> list[str]:
    names = []
    for entry in zone.neighborhoods or []:
        text = entry.get("name") if isinstance(entry, dict) else entry
        if isinstance(text, str) and text.strip():
            names.append(text)
    return names


def find_zone(ctx: ToolContext, address: str) -> DeliveryZone | None:
    """Zona ativa da Company cujo bairro aparece (palavras inteiras) no endereço; vence o bairro mais longo."""
    address_words = words(address)
    best: tuple[int, DeliveryZone] | None = None
    zones = (
        ctx.db.query(DeliveryZone)
        .filter(DeliveryZone.company_id == ctx.company_id, DeliveryZone.is_active.is_(True))
        .all()
    )
    for zone in zones:
        for name in _neighborhood_names(zone):
            target = words(name)
            if not target:
                continue
            size = len(target)
            for start in range(len(address_words) - size + 1):
                if address_words[start : start + size] == target and (best is None or size > best[0]):
                    best = (size, zone)
    return best[1] if best else None


def require_zone(ctx: ToolContext, address: str) -> DeliveryZone:
    zone = find_zone(ctx, address)
    if zone:
        return zone
    active = (
        ctx.db.query(DeliveryZone)
        .filter(DeliveryZone.company_id == ctx.company_id, DeliveryZone.is_active.is_(True))
        .all()
    )
    if not active:
        raise OrderError("Entrega indisponível: não há bairro com zona de entrega cadastrado. Ofereça retirada.")
    neighborhoods = ", ".join(n for z in active for n in _neighborhood_names(z))
    raise OrderError(
        f"Não entregamos nesse bairro. Bairros atendidos: {neighborhoods}. Ofereça outro endereço ou retirada."
    )


# ---------- Order ----------


def _company(ctx: ToolContext) -> Company:
    company = ctx.db.get(Company, ctx.company_id)
    if company is None:
        raise OrderError("Empresa não encontrada.")
    return company


def _active_order(ctx: ToolContext) -> CustomerOrder | None:
    return (
        ctx.db.query(CustomerOrder)
        .filter(CustomerOrder.conversation_id == ctx.conversation_id, CustomerOrder.status.in_(ACTIVE_STATUSES))
        .order_by(CustomerOrder.created_at.desc())
        .first()
    )


def _new_order(ctx: ToolContext) -> CustomerOrder:
    contact = ctx.db.get(Contact, ctx.contact_id)
    order = CustomerOrder(
        order_number=f"{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        conversation_id=ctx.conversation_id,
        instance_id=ctx.instance_id,
        contact_id=ctx.contact_id,
        remote_jid=ctx.remote_jid,
        customer_phone=contact.phone_number if contact else None,
        status="open",
        delivery_fee=Decimal("0.00"),
        total_amount=Decimal("0.00"),
    )
    ctx.db.add(order)
    ctx.db.flush()
    return order


def _subtotal(order: CustomerOrder) -> Decimal:
    return sum((_cents(l.unit_price) * l.quantity for l in order.items), Decimal("0.00"))


def _recompute(ctx: ToolContext, order: CustomerOrder) -> None:
    """Total = itens + taxa da zona (só entrega com endereço numa zona da Company)."""
    for line in order.items:
        line.subtotal_price = _cents(line.unit_price) * line.quantity
    fee = Decimal("0.00")
    if order.delivery_type == "entrega" and order.customer_address:
        zone = find_zone(ctx, order.customer_address)
        fee = _cents(zone.delivery_fee) if zone else fee
    order.delivery_fee = fee
    order.total_amount = _subtotal(order) + fee


def _missing(order: CustomerOrder) -> list[str]:
    missing = []
    if not order.customer_name:
        missing.append("nome")
    if not order.delivery_type:
        missing.append("tipo_entrega")
    elif order.delivery_type == "entrega" and not order.customer_address:
        missing.append("endereco")
    if not order.payment_method:
        missing.append("forma_pagamento")
    return missing


def _view(order: CustomerOrder) -> dict[str, Any]:
    return {
        "numero": order.order_number,
        "status": order.status,
        "status_descricao": STATUS_LABELS.get(order.status, order.status),
        "itens": [
            {
                "item_id": line.menu_item_id,
                "nome": line.item_name,
                "quantidade": line.quantity,
                "preco_unitario": float(line.unit_price),
                "subtotal": float(line.subtotal_price),
                "observacao": line.notes,
            }
            for line in order.items
        ],
        "subtotal": float(_subtotal(order)),
        "taxa_entrega": float(order.delivery_fee or 0),
        "total": float(order.total_amount or 0),
        "nome": order.customer_name,
        "tipo_entrega": order.delivery_type,
        "endereco": order.customer_address,
        "forma_pagamento": order.payment_method,
        "troco_para": float(order.change_for) if order.change_for is not None else None,
        "faltando": _missing(order) if order.status in ACTIVE_STATUSES else [],
    }


# ---------- ações ----------


def _catalog_item(ctx: ToolContext, item_id: Any) -> MenuItem:
    item = (
        ctx.db.query(MenuItem)
        .join(MenuCatalog, MenuCatalog.id == MenuItem.catalog_id)
        .filter(MenuItem.id == str(item_id or ""), MenuCatalog.company_id == ctx.company_id)
        .first()
    )
    if item is None:
        raise OrderError("Item não encontrado no cardápio. Use buscar_cardapio e passe o id do item.")
    if not item.is_available or item.price is None:
        raise OrderError(f"{item.name} está indisponível no momento. Ofereça outro item.")
    return item


def _adicionar_item(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    item = _catalog_item(ctx, args.get("item_id"))
    quantity = _positive_int(args.get("quantidade"), "quantidade", 1)
    note = " ".join(str(args.get("observacao") or "").split()) or None

    order = _active_order(ctx) or _new_order(ctx)
    line = next((l for l in order.items if l.menu_item_id == item.id and (l.notes or None) == note), None)
    if line:
        line.quantity += quantity
    else:
        order.items.append(
            CustomerOrderItem(
                menu_item_id=item.id,
                item_name=item.name,
                quantity=quantity,
                unit_price=_cents(item.price),
                subtotal_price=Decimal("0.00"),
                notes=note,
                sort_order=len(order.items),
            )
        )
    _recompute(ctx, order)
    ctx.db.commit()
    return {"pedido": _view(order)}


def _remover_item(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    order = _active_order(ctx)
    item_id = str(args.get("item_id") or "")
    lines = [l for l in (order.items if order else []) if l.menu_item_id == item_id]
    if not lines:
        raise OrderError("Esse item não está no pedido.")
    quantity = _positive_int(args.get("quantidade"), "quantidade", None)

    if quantity is None or quantity >= lines[0].quantity and len(lines) == 1:
        for line in lines:
            order.items.remove(line)
    else:
        lines[0].quantity -= min(quantity, lines[0].quantity)
        if lines[0].quantity <= 0:
            order.items.remove(lines[0])
    _recompute(ctx, order)
    ctx.db.commit()
    return {"pedido": _view(order)}


def _ver(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    order = _active_order(ctx)
    if order is None:
        return {"pedido": None, "mensagem": "Não há pedido em aberto."}
    return {"pedido": _view(order)}


def _definir_dados(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    order = _active_order(ctx)
    if order is None:
        raise OrderError("Não há pedido em aberto. Adicione um item antes de informar os dados.")
    company = _company(ctx)

    name = validate_name(args["nome"]) if args.get("nome") is not None else order.customer_name
    delivery_type = (
        _choice(args["tipo_entrega"], DELIVERY_TYPES, "tipo_entrega")
        if args.get("tipo_entrega") is not None
        else order.delivery_type
    )
    payment = (
        _choice(args["forma_pagamento"], PAYMENT_METHODS, "forma_pagamento")
        if args.get("forma_pagamento") is not None
        else order.payment_method
    )
    if payment == "pix" and not company.pix_key:
        raise OrderError("Esta empresa não aceita Pix. Ofereça dinheiro ou cartão.")

    address = order.customer_address
    if delivery_type == "retirada":
        address = None
    elif args.get("endereco") is not None:
        address = validate_address(args["endereco"])
    if delivery_type == "entrega" and address:
        require_zone(ctx, address)

    change_for = order.change_for
    if args.get("troco_para") is not None:
        try:
            change_for = _cents(Decimal(str(args["troco_para"])))
        except InvalidOperation:
            raise OrderError("troco_para deve ser um valor em reais.") from None
        if change_for <= 0:
            raise OrderError("troco_para deve ser maior que zero.")
    if payment != "dinheiro":
        change_for = None if args.get("troco_para") is None else change_for
    if change_for is not None and payment != "dinheiro":
        raise OrderError("troco_para só vale para pagamento em dinheiro.")

    if all(args.get(k) is None for k in ("nome", "tipo_entrega", "forma_pagamento", "endereco", "troco_para")):
        raise OrderError("Informe ao menos um dado: nome, tipo_entrega, endereco, forma_pagamento ou troco_para.")

    order.customer_name = name
    order.delivery_type = delivery_type
    order.customer_address = address
    order.payment_method = payment
    order.change_for = change_for
    _recompute(ctx, order)
    if change_for is not None and change_for < order.total_amount:
        raise OrderError(f"O troco é para {brl(change_for)}, menos que o total de {brl(order.total_amount)}.")
    ctx.db.commit()
    return {"pedido": _view(order)}


def _finalizar(ctx: ToolContext, _args: dict[str, Any]) -> dict[str, Any]:
    order = _active_order(ctx)
    if order is None or not order.items:
        raise OrderError("O pedido está vazio. Adicione itens antes de finalizar.")
    missing = _missing(order)
    if missing:
        raise OrderError(f"Faltam dados para finalizar: {', '.join(missing)}.")
    company = _company(ctx)

    if order.delivery_type == "entrega":
        require_zone(ctx, order.customer_address)
    _recompute(ctx, order)

    minimum = _cents(company.minimum_order) if company.minimum_order else None
    subtotal = _subtotal(order)
    if minimum and subtotal < minimum:
        raise OrderError(
            f"Pedido mínimo de {brl(minimum)} em itens (sem a taxa de entrega); faltam {brl(minimum - subtotal)}."
        )
    if order.change_for is not None and order.change_for < order.total_amount:
        raise OrderError(f"O troco é para {brl(order.change_for)}, menos que o total de {brl(order.total_amount)}.")
    if order.payment_method == "pix" and not company.pix_key:
        raise OrderError("Esta empresa não tem chave Pix cadastrada; não dá para fechar com Pix.")

    record = pix.ensure_payment_record(ctx.db, order, company) if order.payment_method == "pix" else None
    order.status = "closed"
    order.closed_at = datetime.now(timezone.utc)
    ctx.db.commit()

    result: dict[str, Any] = {
        "pedido": _view(order),
        "mensagem": f"Pedido {order.order_number} confirmado. Total {brl(order.total_amount)}.",
    }
    if record is not None:
        result["pix"] = {
            "valor": float(record.amount),
            "chave": record.pix_key,
            "txid": pix.txid_for(order),
            "copia_e_cola": record.qr_code_data,
        }
    return result


_ACTION_HANDLERS = {
    "adicionar_item": _adicionar_item,
    "remover_item": _remover_item,
    "ver": _ver,
    "definir_dados": _definir_dados,
    "finalizar": _finalizar,
}


async def _gerenciar_pedido(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    handler = _ACTION_HANDLERS.get(str(args.get("acao") or ""))
    if handler is None:
        return _error(f"Ação inválida. Use: {', '.join(ACTIONS)}.")
    try:
        return _ok(handler(ctx, args))
    except OrderError as exc:
        ctx.db.rollback()
        return _error(str(exc))


async def _status_pedido(ctx: ToolContext, _args: dict[str, Any]) -> ToolResult:
    order = (
        ctx.db.query(CustomerOrder)
        .filter(CustomerOrder.contact_id == ctx.contact_id, CustomerOrder.instance_id == ctx.instance_id)
        .order_by(CustomerOrder.opened_at.desc(), CustomerOrder.created_at.desc())
        .first()
    )
    if order is None:
        return _ok({"pedido": None, "mensagem": "Este cliente ainda não fez nenhum pedido."})
    return _ok({"pedido": _view(order)})


def gerenciar_pedido_tool() -> Tool:
    return Tool(
        name="gerenciar_pedido",
        description=(
            "Monta e fecha o pedido do cliente. Ações: adicionar_item (item_id vindo de buscar_cardapio, "
            "quantidade, observacao), remover_item (item_id, quantidade opcional), ver, definir_dados (nome, "
            "tipo_entrega, endereco, forma_pagamento, troco_para) e finalizar. Só finalize com o pedido e os "
            "dados completos; o total inclui a taxa de entrega e respeita o pedido mínimo."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "acao": {"type": "string", "enum": ACTIONS},
                "item_id": {"type": "string", "description": "Id do item, vindo de buscar_cardapio."},
                "quantidade": {"type": "integer", "minimum": 1},
                "observacao": {"type": "string", "description": "Ex: 'sem cebola'."},
                "nome": {"type": "string", "description": "Nome do cliente."},
                "endereco": {"type": "string", "description": "Rua, número e bairro. Só para entrega."},
                "tipo_entrega": {"type": "string", "enum": DELIVERY_TYPES},
                "forma_pagamento": {"type": "string", "enum": PAYMENT_METHODS},
                "troco_para": {"type": "number", "description": "Valor da nota, se pagar em dinheiro e precisar de troco."},
            },
            "required": ["acao"],
            "additionalProperties": False,
        },
        handler=_gerenciar_pedido,
    )


def status_pedido_tool() -> Tool:
    return Tool(
        name="status_pedido",
        description=(
            "Mostra o último pedido deste cliente: status, itens e total. "
            "Use para 'cadê meu pedido', 'já saiu?' e perguntas parecidas."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=_status_pedido,
    )
