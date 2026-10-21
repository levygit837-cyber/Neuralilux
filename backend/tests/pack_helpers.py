"""Cenário compartilhado dos testes do núcleo (core_tools) e do Pack catálogo & pedidos.

Monta duas Companies isoladas (a do contexto e uma "outra") para provar escopo por `company_id`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.models.models import (
    Company,
    Contact,
    Conversation,
    DeliveryZone,
    Instance,
    MenuCatalog,
    MenuCategory,
    MenuItem,
)

BUSINESS_HOURS = {
    "mon": [["18:00", "23:00"]],
    "tue": [["18:00", "23:00"]],
    "wed": [["18:00", "23:00"]],
    "thu": [["18:00", "23:00"]],
    "fri": [["18:00", "00:00"]],
    "sat": [["18:00", "00:00"]],
    "sun": [["18:00", "23:00"]],
}


@dataclass
class World:
    db: object
    company: Company
    other_company: Company
    instance: Instance
    contact: Contact
    conversation: Conversation
    items: dict[str, MenuItem]
    other_company_item: MenuItem
    ctx: ToolContext


def _catalog(db, company: Company, categories: dict[str, list[tuple]]) -> dict[str, MenuItem]:
    catalog = MenuCatalog(company_id=company.id, name=f"Cardápio {company.name}")
    db.add(catalog)
    db.flush()
    items: dict[str, MenuItem] = {}
    for order, (category_name, rows) in enumerate(categories.items()):
        category = MenuCategory(catalog_id=catalog.id, name=category_name, sort_order=order)
        db.add(category)
        db.flush()
        for name, price, available, description in rows:
            item = MenuItem(
                catalog_id=catalog.id,
                category_id=category.id,
                name=name,
                price=Decimal(price),
                is_available=available,
                description=description,
            )
            db.add(item)
            db.flush()
            items[name] = item
    return items


def make_world(db, *, with_zone: bool = True, pix_key: str | None = "pix@macedos.example") -> World:
    company = Company(
        name="Macedos",
        address_street="Rua das Flores",
        address_number="100",
        address_neighborhood="Centro",
        address_city="Fortaleza",
        address_state="CE",
        phone="(85) 99999-0000",
        pix_key=pix_key,
        business_hours=BUSINESS_HOURS,
        timezone="America/Fortaleza",
        minimum_order=Decimal("30.00"),
    )
    other_company = Company(name="Outra Pizzaria", pix_key="outra@pix.example")
    db.add_all([company, other_company])
    db.flush()

    instance = Instance(name="inst-macedos", evolution_instance_id="evo-macedos", company_id=company.id)
    db.add(instance)
    db.flush()
    contact = Contact(
        instance_id=instance.id,
        phone_number="5585988887777",
        remote_jid="5585988887777@s.whatsapp.net",
        name="Cliente Teste",
    )
    db.add(contact)
    db.flush()
    conversation = Conversation(
        instance_id=instance.id,
        contact_id=contact.id,
        remote_jid=contact.remote_jid,
    )
    db.add(conversation)

    items = _catalog(
        db,
        company,
        {
            "Pizzas": [
                ("Pizza Toscana", "45.00", True, "Calabresa, cebola e mussarela"),
                ("Pizza Calabresa", "40.00", True, None),
                ("Pizza Portuguesa", "48.00", False, "Presunto, ovos e cebola"),
            ],
            "Bebidas": [
                ("Refrigerante Cola 2L", "12.00", True, None),
                ("Suco de Laranja", "9.50", True, None),
            ],
            "Brindes": [("Camiseta Pizzaiolo", "30.00", True, None)],
        },
    )
    other_items = _catalog(db, other_company, {"Pizzas": [("Pizza Toscana", "99.00", True, None)]})

    if with_zone:
        db.add(
            DeliveryZone(
                company_id=company.id,
                name="Centro",
                neighborhoods=["Centro", "Aldeota"],
                delivery_fee=Decimal("5.00"),
                minimum_order_value=Decimal("0"),
            )
        )
    # Zona de outra Company e zona legada sem dono: nunca podem entrar nas contas da Macedos.
    db.add(
        DeliveryZone(company_id=other_company.id, name="Praia", neighborhoods=["Praia"], delivery_fee=Decimal("50.00"))
    )
    db.add(DeliveryZone(company_id=None, name="Legada", neighborhoods=["Meireles"], delivery_fee=Decimal("77.00")))
    db.commit()

    ctx = ToolContext(
        db=db,
        company_id=company.id,
        instance_id=instance.id,
        conversation_id=conversation.id,
        contact_id=contact.id,
        remote_jid=contact.remote_jid,
    )
    return World(
        db=db,
        company=company,
        other_company=other_company,
        instance=instance,
        contact=contact,
        conversation=conversation,
        items=items,
        other_company_item=other_items["Pizza Toscana"],
        ctx=ctx,
    )


def tool_named(tools: list[Tool], name: str) -> Tool:
    return next(t for t in tools if t.name == name)


async def call(tool: Tool, ctx: ToolContext, **arguments) -> ToolResult:
    return await tool.handler(ctx, arguments)


def payload(result: ToolResult) -> dict:
    return json.loads(result.content)


ENDERECO = "Rua das Flores 123, Centro"


def order_of(world):
    """O único Order da Conversation do `world`, relido do banco."""
    from app.models.models import CustomerOrder

    world.db.expire_all()
    return world.db.query(CustomerOrder).filter_by(conversation_id=world.conversation.id).one()


async def add_item(world, pedido, name="Pizza Toscana", **kw):
    return await call(pedido, world.ctx, acao="adicionar_item", item_id=world.items[name].id, **kw)


async def fill_delivery(world, pedido, **overrides):
    data = dict(nome="Maria Silva", endereco=ENDERECO, tipo_entrega="entrega", forma_pagamento="dinheiro")
    data.update(overrides)
    return await call(pedido, world.ctx, acao="definir_dados", **data)
