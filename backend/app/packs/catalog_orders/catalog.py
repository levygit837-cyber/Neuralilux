"""`buscar_cardapio`: busca de Catalog Items da Company do contexto.

Normalização sem acento, tokens que casam palavra inteira (com plural simples) no nome ou na categoria.
Só entram itens disponíveis de catálogos ativos da `ctx.company_id`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.models import MenuCatalog, MenuCategory, MenuItem

MAX_RESULTS = 15
MAX_DESCRIPTION = 120

_WORD = re.compile(r"[a-z0-9]+")


def normalize(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def words(text: str | None) -> list[str]:
    return _WORD.findall(normalize(text))


def singular(word: str) -> str:
    """Plural simples do português: 'pizzas' -> 'pizza'. Palavras curtas ('gas', '2l') ficam como estão."""
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def _matches_all(tokens: list[str], candidate_words: list[str]) -> bool:
    singulars = {singular(w) for w in candidate_words}
    return all(singular(token) in singulars for token in tokens)


def _short(description: str | None) -> str | None:
    text = " ".join((description or "").split())
    if not text:
        return None
    return text if len(text) <= MAX_DESCRIPTION else text[: MAX_DESCRIPTION - 1].rstrip() + "…"


def _available_rows(ctx: ToolContext) -> list[tuple[MenuItem, MenuCategory]]:
    return (
        ctx.db.query(MenuItem, MenuCategory)
        .join(MenuCatalog, MenuCatalog.id == MenuItem.catalog_id)
        .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
        .filter(
            MenuCatalog.company_id == ctx.company_id,
            MenuCatalog.is_active.is_(True),
            MenuItem.is_available.is_(True),
            MenuItem.price.isnot(None),
        )
        .order_by(MenuCategory.sort_order, MenuCategory.name, MenuItem.sort_order, MenuItem.name)
        .all()
    )


async def _buscar_cardapio(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    query_tokens = words(args.get("consulta"))
    category_tokens = words(args.get("categoria"))

    rows = _available_rows(ctx)
    categories: list[str] = []
    for _, category in rows:
        if category.name not in categories:
            categories.append(category.name)

    found = []
    for item, category in rows:
        category_words = words(category.name)
        if category_tokens and not _matches_all(category_tokens, category_words):
            continue
        if query_tokens and not _matches_all(query_tokens, words(item.name) + category_words):
            continue
        found.append((item, category))

    data = {
        "categorias": categories,
        "total_encontrado": len(found),
        "itens": [
            {
                "id": item.id,
                "nome": item.name,
                "preco": float(item.price),
                "descricao": _short(item.description),
                "categoria": category.name,
            }
            for item, category in found[:MAX_RESULTS]
        ],
    }
    return ToolResult(content=json.dumps(data, ensure_ascii=False))


def buscar_cardapio_tool() -> Tool:
    return Tool(
        name="buscar_cardapio",
        description=(
            "Busca itens disponíveis no cardápio da empresa. Chame SEMPRE antes de citar preço ou item. "
            "Todas as palavras da consulta têm de aparecer no nome ou na categoria. Sem argumentos, lista as "
            "categorias e os primeiros itens. Devolve até 15 itens com id, nome, preço e descrição."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Palavras do item procurado, ex: 'pizza toscana'."},
                "categoria": {"type": "string", "description": "Nome da categoria para filtrar, ex: 'bebidas'."},
            },
            "additionalProperties": False,
        },
        handler=_buscar_cardapio,
    )
