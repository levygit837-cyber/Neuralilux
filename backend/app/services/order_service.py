from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.models import Contact, Conversation, CustomerOrder, CustomerOrderItem, Instance
from app.services.menu_catalog_service import find_menu_item


ACTIVE_ORDER_STATUSES = ("open", "collecting_data", "ready_for_confirmation")

FIELD_LABELS = {
    "nome": "nome",
    "endereco": "endereco",
    "telefone": "telefone",
    "pagamento": "pagamento",
}


class OrderServiceError(Exception):
    """Raised when an order operation cannot be completed."""


def _discover_orders_output_dir() -> Path:
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        candidate = parent / "output" / "orders"
        if candidate.parent.exists():
            return candidate
    return current_file.parents[2] / "output" / "orders"


ORDERS_OUTPUT_DIR = _discover_orders_output_dir()


def _generate_order_number() -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:6].upper()
    return f"{date_part}-{suffix}"


def _get_conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = (
        db.query(Conversation)
        .options(joinedload(Conversation.contact), joinedload(Conversation.instance))
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conversation:
        raise OrderServiceError("Conversa não encontrada para abrir a comanda.")
    return conversation


def get_active_order(db: Session, conversation_id: str) -> Optional[CustomerOrder]:
    return (
        db.query(CustomerOrder)
        .options(joinedload(CustomerOrder.items))
        .filter(
            CustomerOrder.conversation_id == conversation_id,
            CustomerOrder.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .order_by(CustomerOrder.created_at.desc())
        .first()
    )


def _get_or_create_active_order(db: Session, conversation_id: str) -> CustomerOrder:
    order = get_active_order(db, conversation_id)
    if order:
        return order

    conversation = _get_conversation(db, conversation_id)
    order = CustomerOrder(
        order_number=_generate_order_number(),
        conversation_id=conversation.id,
        instance_id=conversation.instance_id,
        contact_id=conversation.contact_id,
        remote_jid=conversation.remote_jid,
        status="open",
        total_amount=Decimal("0.00"),
    )
    db.add(order)
    db.flush()
    return order


def _missing_required_fields(order: CustomerOrder) -> list[str]:
    missing = []
    if not (order.customer_name or "").strip():
        missing.append("nome")
    if not (order.customer_address or "").strip():
        missing.append("endereco")
    if not (order.customer_phone or "").strip():
        missing.append("telefone")
    if not (order.payment_method or "").strip():
        missing.append("pagamento")
    return missing


def get_next_missing_field(order: Optional[CustomerOrder]) -> Optional[str]:
    if not order:
        return None
    missing = _missing_required_fields(order)
    return missing[0] if missing else None


def _refresh_order_total(order: CustomerOrder) -> None:
    total = Decimal("0.00")
    for item in order.items:
        subtotal = Decimal(str(item.unit_price or 0)) * int(item.quantity or 0)
        item.subtotal_price = subtotal.quantize(Decimal("0.01"))
        total += item.subtotal_price
    order.total_amount = total.quantize(Decimal("0.01"))


def _sync_order_status(order: CustomerOrder, *, preserve_checkout_state: bool = True) -> None:
    if order.status in {"closed", "cancelled"}:
        return
    if preserve_checkout_state and order.status in {"collecting_data", "ready_for_confirmation"}:
        order.status = "ready_for_confirmation" if not _missing_required_fields(order) else "collecting_data"
        return
    order.status = "open"


def serialize_order(order: CustomerOrder) -> dict[str, Any]:
    return {
        "id": order.id,
        "numero_pedido": order.order_number,
        "status": order.status,
        "itens": [
            {
                "id": item.id,
                "quantidade": item.quantity,
                "nome": item.item_name,
                "preco_unitario": float(item.unit_price or 0),
                "subtotal": float(item.subtotal_price or 0),
                "observacao": item.notes,
            }
            for item in order.items
        ],
        "total": float(order.total_amount or 0),
        "cliente_nome": order.customer_name,
        "cliente_endereco": order.customer_address,
        "cliente_telefone": order.customer_phone,
        "forma_pagamento": order.payment_method,
        "opened_at": order.opened_at.isoformat() if order.opened_at else None,
        "closed_at": order.closed_at.isoformat() if order.closed_at else None,
        "remote_jid": order.remote_jid,
        "export_path": order.export_path,
    }


def order_items_snapshot(order: Optional[CustomerOrder]) -> list[dict[str, Any]]:
    if not order:
        return []
    return [
        {
            "produto_id": item.menu_item_id or item.id,
            "nome": item.item_name,
            "quantidade": item.quantity,
            "preco_unitario": float(item.unit_price or 0),
            "observacao": item.notes,
        }
        for item in order.items
    ]


def add_item_to_order(
    db: Session,
    conversation_id: str,
    item_name: str,
    quantity: int = 1,
    notes: str = "",
    check_stock: bool = False,
) -> CustomerOrder:
    if not item_name.strip():
        raise OrderServiceError("Informe o item que deseja adicionar.")

    product = find_menu_item(item_name, db=db)
    if not product:
        raise OrderServiceError(f"Item '{item_name}' não encontrado no cardápio.")
    if check_stock and not product.is_available:
        raise OrderServiceError(f"Item '{product.name}' está indisponível no momento.")

    if quantity < 1:
        quantity = 1

    order = _get_or_create_active_order(db, conversation_id)
    existing_item = next(
        (
            item
            for item in order.items
            if (item.menu_item_id and item.menu_item_id == str(product.id))
            or item.item_name.lower() == product.name.lower()
        ),
        None,
    )

    if existing_item:
        existing_item.quantity += quantity
        if notes:
            existing_item.notes = notes
    else:
        order.items.append(
            CustomerOrderItem(
                menu_item_id=str(product.id),
                item_name=product.name,
                quantity=quantity,
                unit_price=Decimal(str(product.price or 0)).quantize(Decimal("0.01")),
                subtotal_price=Decimal("0.00"),
                notes=notes or None,
                sort_order=len(order.items) + 1,
            )
        )

    _refresh_order_total(order)
    _sync_order_status(order)
    db.commit()
    db.refresh(order)
    return get_active_order(db, conversation_id) or order


def remove_item_from_order(db: Session, conversation_id: str, item_name: str) -> CustomerOrder:
    order = get_active_order(db, conversation_id)
    if not order or not order.items:
        raise OrderServiceError("Seu pedido está vazio.")

    item_name_lower = item_name.lower().strip()
    target = next((item for item in order.items if item_name_lower in item.item_name.lower()), None)
    if not target:
        raise OrderServiceError(f"Item '{item_name}' não encontrado no pedido atual.")

    order.items.remove(target)
    db.delete(target)

    if not order.items:
        order.total_amount = Decimal("0.00")
    else:
        _refresh_order_total(order)
    _sync_order_status(order)
    db.commit()
    db.refresh(order)
    return get_active_order(db, conversation_id) or order


def cancel_active_order(db: Session, conversation_id: str) -> Optional[CustomerOrder]:
    order = get_active_order(db, conversation_id)
    if not order:
        return None
    order.status = "cancelled"
    order.closed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)
    return order


def update_customer_field(
    db: Session,
    conversation_id: str,
    field_name: str,
    value: str,
) -> CustomerOrder:
    order = get_active_order(db, conversation_id)
    if not order:
        raise OrderServiceError("Nenhuma comanda aberta para atualizar.")

    cleaned_value = value.strip()
    if field_name == "nome":
        order.customer_name = cleaned_value
    elif field_name == "endereco":
        order.customer_address = cleaned_value
    elif field_name == "telefone":
        digits = "".join(char for char in cleaned_value if char.isdigit())
        order.customer_phone = digits or cleaned_value
    elif field_name == "pagamento":
        order.payment_method = cleaned_value
    else:
        raise OrderServiceError("Campo de coleta inválido.")

    order.status = "ready_for_confirmation" if not _missing_required_fields(order) else "collecting_data"
    db.commit()
    db.refresh(order)
    return get_active_order(db, conversation_id) or order


def begin_checkout(db: Session, conversation_id: str) -> CustomerOrder:
    order = get_active_order(db, conversation_id)
    if not order or not order.items:
        raise OrderServiceError("Sua comanda está vazia. Me diga o item que deseja pedir.")

    order.status = "ready_for_confirmation" if not _missing_required_fields(order) else "collecting_data"
    db.commit()
    db.refresh(order)
    return get_active_order(db, conversation_id) or order


def confirm_order(db: Session, conversation_id: str) -> CustomerOrder:
    order = get_active_order(db, conversation_id)
    if not order or not order.items:
        raise OrderServiceError("Não encontrei uma comanda aberta para confirmar.")

    missing = _missing_required_fields(order)
    if missing:
        order.status = "collecting_data"
        db.commit()
        db.refresh(order)
        raise OrderServiceError(f"Faltam dados para fechar a comanda: {', '.join(FIELD_LABELS[field] for field in missing)}.")

    order.status = "closed"
    order.closed_at = datetime.now(timezone.utc)
    db.flush()
    export_path = export_order_to_json(order)
    order.export_path = str(export_path)
    db.commit()
    db.refresh(order)
    return order


def export_order_to_json(order: CustomerOrder) -> Path:
    ORDERS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = serialize_order(order)
    filename = f"{order.order_number}.json"
    file_path = ORDERS_OUTPUT_DIR / filename
    with file_path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)
    return file_path


def build_collection_prompt(order: CustomerOrder) -> dict[str, Any]:
    next_field = get_next_missing_field(order)
    if not next_field:
        return {
            "etapa": "confirmacao",
            "mensagem": "Se estiver tudo certo, responda CONFIRMAR para fechar o pedido.",
            "dados_coletados": {
                "nome": order.customer_name,
                "endereco": order.customer_address,
                "telefone": order.customer_phone,
                "pagamento": order.payment_method,
            },
            "proxima_etapa": "confirmacao",
        }

    prompts = {
        "nome": "Para finalizar, me diga seu nome para a comanda.",
        "endereco": "Agora me passe o endereço de entrega.",
        "telefone": "Qual telefone devo registrar para contato?",
        "pagamento": "Como prefere pagar? PIX, dinheiro, débito ou crédito?",
    }
    return {
        "etapa": next_field,
        "mensagem": prompts[next_field],
        "dados_coletados": {
            "nome": order.customer_name,
            "endereco": order.customer_address,
            "telefone": order.customer_phone,
            "pagamento": order.payment_method,
        },
        "proxima_etapa": next_field,
    }
