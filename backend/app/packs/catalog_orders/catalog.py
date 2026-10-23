"""`buscar_cardapio`: busca de Catalog Items da Company do contexto.

Normalização sem acento e palavras inteiras (com plural simples). Palavras vazias não contam. Cada item é
pontuado pelas palavras da consulta que aparecem no nome, na descrição curta ou na categoria (com os sinônimos
de categoria do Pack); item que casa mais vem primeiro, e basta casar uma palavra para entrar. Sem consulta nem
categoria, devolve só as categorias com a contagem de itens.
Só entram itens disponíveis de catálogos ativos da `ctx.company_id`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any

from app.agent import clock
from app.agent.contracts import Tool, ToolContext, ToolResult
from app.models import Company, MenuCatalog, MenuCategory, MenuItem
from app.services.menu.availability import schedule_note

MAX_RESULTS = 15
MAX_DESCRIPTION = 120

_WORD = re.compile(r"[a-z0-9]+")

# Palavras que o cliente usa para ligar a frase e que nunca identificam um item ("pizza de calabresa").
STOPWORDS = frozenset(
    "a as o os um uma uns umas de da do das dos com e em no na nos nas pra para por quero queria".split()
)

# Nome genérico que o cliente usa -> categoria do cardápio. Chave: palavra da categoria no singular, sem acento.
# É vocabulário do ramo restaurante, por isso mora no Pack e não no núcleo (ADR 0004).
CATEGORY_SYNONYMS: dict[str, tuple[str, ...]] = {
    "bebida": ("refrigerante", "refri", "drink"),
    "pasta": ("massa", "macarrao"),
    "sobremesa": ("doce",),
    "porcao": ("petisco",),
    "acompanhamento": ("guarnicao",),
    "entrada": ("aperitivo",),
    "sopa": ("caldo",),
    "ave": ("frango", "galinha"),
}


def normalize(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def words(text: str | None) -> list[str]:
    return _WORD.findall(normalize(text))


def singular(word: str) -> str:
    """Plural simples do português: 'pizzas' -> 'pizza'. Palavras curtas ('gas', '2l') ficam como estão."""
    if len(word) > 4 and word.endswith("oes"):
        return word[:-3] + "ao"
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def search_tokens(text: str | None) -> list[str]:
    """Palavras da consulta no singular, sem palavras vazias e sem repetição, na ordem em que foram escritas."""
    return list(dict.fromkeys(singular(w) for w in words(text) if w not in STOPWORDS))


def _terms(text: str | None) -> set[str]:
    return {singular(w) for w in words(text)}


def _category_terms(category_name: str) -> set[str]:
    terms = _terms(category_name)
    for term in list(terms):
        terms.update(CATEGORY_SYNONYMS.get(term, ()))
    return terms


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


def _category_counts(rows: list[tuple[MenuItem, MenuCategory]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for _, category in rows:
        counts[category.name] = counts.get(category.name, 0) + 1
    return [{"nome": name, "itens": count} for name, count in counts.items()]


def _rank(
    rows: list[tuple[MenuItem, MenuCategory]], query_tokens: list[str], category_tokens: list[str]
) -> list[tuple[MenuItem, MenuCategory]]:
    """Itens que casam ao menos uma palavra da consulta. Mais palavras casadas vêm primeiro; no empate, quem casa
    no nome vem antes de quem casa na categoria, e esse antes de quem só casa na descrição."""
    ranked: list[tuple[tuple[int, int, int], MenuItem, MenuCategory]] = []
    for item, category in rows:
        category_terms = _category_terms(category.name)
        if category_tokens and not all(token in category_terms for token in category_tokens):
            continue
        name_terms = _terms(item.name)
        searchable = name_terms | _terms(_short(item.description)) | category_terms
        matched = sum(token in searchable for token in query_tokens)
        if query_tokens and not matched:
            continue
        in_name = sum(token in name_terms for token in query_tokens)
        in_category = sum(token in category_terms for token in query_tokens)
        ranked.append(((-matched, -in_name, -in_category), item, category))
    ranked.sort(key=lambda entry: entry[0])  # estável: empates seguem a ordem do cardápio
    return [(item, category) for _, item, category in ranked]


async def _buscar_cardapio(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    query_tokens = search_tokens(args.get("consulta"))
    category_tokens = search_tokens(args.get("categoria"))

    rows = _available_rows(ctx)
    data: dict[str, Any] = {"categorias": _category_counts(rows)}
    if not query_tokens and not category_tokens:
        data["itens"] = []
        data["aviso"] = "Sem consulta nem categoria só voltam as categorias. Busque por uma palavra ou por uma categoria."
        return ToolResult(content=json.dumps(data, ensure_ascii=False))

    company = ctx.db.get(Company, ctx.company_id)
    now_local = clock.utc_now().astimezone(clock.company_zone(company)) if company else None
    found = _rank(rows, query_tokens, category_tokens)
    data.update(
        {
            "total_encontrado": len(found),
            "itens": [_item_entry(item, category, now_local) for item, category in found[:MAX_RESULTS]],
        }
    )
    return ToolResult(content=json.dumps(data, ensure_ascii=False))


def _item_entry(item: MenuItem, category: MenuCategory, now_local: datetime | None) -> dict[str, Any]:
    entry = {
        "id": item.id,
        "nome": item.name,
        "preco": float(item.price),
        "descricao": _short(item.description),
        "categoria": category.name,
    }
    note = schedule_note(item.raw_payload, now_local) if now_local else None
    if note:
        entry["disponibilidade"] = note
    return entry


def buscar_cardapio_tool() -> Tool:
    return Tool(
        name="buscar_cardapio",
        description=(
            "Busca itens disponíveis no cardápio da empresa. Chame SEMPRE antes de citar preço ou item. "
            "Basta uma palavra da consulta aparecer no nome, na descrição ou na categoria: quem casa mais palavras "
            "vem primeiro. Nomes genéricos como 'refrigerante' ou 'massa' encontram a categoria. Sem consulta nem "
            "categoria, devolve só as categorias com a quantidade de itens. Devolve até 15 itens com id, nome, "
            "preço e descrição; item com horário próprio que está fora dele agora traz também `disponibilidade`."
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
