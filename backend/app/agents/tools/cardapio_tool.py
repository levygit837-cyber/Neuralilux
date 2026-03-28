"""
Cardapio Tool - Consulta estruturada do cardápio Macedos.
Usa o banco quando a estrutura já foi sincronizada e cai para o JSON local quando necessário.
"""
from typing import Any, Iterable

from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.services.menu_catalog_service import (
    MenuCategoryRecord,
    MenuItemRecord,
    MenuSnapshot,
    filter_items_by_category,
    get_menu_snapshot,
    normalize_text,
)


MAX_CATEGORIES_PREVIEW = 6
MAX_CATEGORY_ITEMS_PREVIEW = 6
MAX_SEARCH_ITEMS_PREVIEW = 5
MAX_FULL_MENU_ITEMS = 15


def _get_db() -> Session:
    return SessionLocal()


def _format_price(price: Any | None) -> str:
    if price is None:
        return "Preço sob consulta"
    return f"R$ {float(price):.2f}".replace(".", ",")


def _available_items(items: Iterable[MenuItemRecord]) -> list[MenuItemRecord]:
    # Retorna todos os itens, sem filtrar por disponibilidade (estoque)
    # O sistema presume que itens estão sempre disponíveis
    return list(items)


def _find_categories(snapshot: MenuSnapshot, category_name: str) -> list[MenuCategoryRecord]:
    normalized_target = normalize_text(category_name)
    if not normalized_target:
        return []

    suggestions: list[MenuCategoryRecord] = []
    for category in snapshot.categories:
        normalized_category = normalize_text(category.name)
        if not normalized_category:
            continue
        if normalized_target in normalized_category or normalized_category in normalized_target:
            suggestions.append(category)
    return suggestions


def _listar_categorias(snapshot: MenuSnapshot) -> str:
    if not snapshot.categories:
        return "Nenhuma categoria encontrada no cardápio."

    lines = ["📋 *CATEGORIAS DO CARDÁPIO*", "━━━━━━━━━━━━", ""]
    preview_categories = snapshot.categories[:MAX_CATEGORIES_PREVIEW]

    for category in preview_categories:
        lines.append(f"🔸 {category.name}")

    remaining = len(snapshot.categories) - len(preview_categories)
    if remaining > 0:
        lines.append("")
        lines.append(f"… e mais {remaining} categorias.")

    lines.append("")
    lines.append("━━━━━━━━━━━━")
    lines.append("💡 Me diga qual categoria você quer ver primeiro.")
    return "\n".join(lines)


def _buscar_por_categoria(snapshot: MenuSnapshot, category_name: str) -> str:
    suggestions = _find_categories(snapshot, category_name)
    if not suggestions:
        return f"Categoria '{category_name}' não encontrada. Posso te mostrar as categorias disponíveis primeiro."

    category = suggestions[0]
    items = filter_items_by_category(_available_items(snapshot.items), category.name)
    if not items:
        return f"Nenhum item disponível na categoria '{category.name}'."

    lines = [f"🍽️ *{category.name.upper()}*", "━━━━━━━━━━━━", ""]
    preview_items = items[:MAX_CATEGORY_ITEMS_PREVIEW]

    for item in preview_items:
        lines.append(f"📌 *{item.name}*")
        if item.description:
            lines.append(f"   _{item.description}_")
        lines.append(f"   💰 {_format_price(item.price)}")
        lines.append("")

    if len(items) > len(preview_items):
        lines.append("━━━━━━━━━━━━")
        lines.append("Se quiser, posso te mostrar mais opções dessa categoria.")
        lines.append("")

    lines.append("💡 Quer adicionar algum item na sua comanda?")
    return "\n".join(lines)


def _buscar_por_termo(snapshot: MenuSnapshot, term: str) -> str:
    normalized_term = normalize_text(term)
    items: list[MenuItemRecord] = []
    for item in _available_items(snapshot.items):
        haystack = " ".join(
            filter(
                None,
                [
                    normalize_text(item.name),
                    normalize_text(item.description),
                    normalize_text(item.category_name),
                ],
            )
        )
        if normalized_term and normalized_term in haystack:
            items.append(item)

    if not items:
        return f"Nenhum item encontrado para '{term}'. Tente outro termo ou peça as categorias."

    lines = [f"🔍 *Resultados para '{term}'*", "━━━━━━━━━━━━", ""]
    preview_items = items[:MAX_SEARCH_ITEMS_PREVIEW]

    for item in preview_items:
        lines.append(f"📌 *{item.name}* ({item.category_name})")
        if item.description:
            lines.append(f"   _{item.description}_")
        lines.append(f"   💰 {_format_price(item.price)}")
        lines.append("")

    if len(items) > len(preview_items):
        lines.append("Posso te mostrar mais opções se quiser.")

    lines.append("💡 Se preferir, posso organizar por categoria.")
    return "\n".join(lines)


def _buscar_item_exato(snapshot: MenuSnapshot, item_name: str) -> str:
    normalized_target = normalize_text(item_name)
    if not normalized_target:
        return "Informe o nome do item que você quer consultar."

    candidates: list[MenuItemRecord] = []
    for item in snapshot.items:
        normalized_name = normalize_text(item.name)
        if normalized_target == normalized_name:
            candidates.insert(0, item)
        elif normalized_target in normalized_name:
            candidates.append(item)

    if not candidates:
        return f"Item '{item_name}' não encontrado no cardápio."

    item = candidates[0]
    lines = [f"📌 *{item.name}*", f"📂 Categoria: {item.category_name}"]
    if item.description:
        lines.append(f"📝 {item.description}")
    lines.append(f"💰 {_format_price(item.price)}")
    return "\n".join(lines)


def _listar_resumo(snapshot: MenuSnapshot) -> str:
    """Lista um resumo do cardápio com categorias disponíveis."""
    if not snapshot.categories:
        return "Nenhuma categoria encontrada no cardápio."

    available_items = _available_items(snapshot.items)
    if not available_items:
        return "Nenhum item disponível no cardápio no momento."

    lines = ["📋 *NOSSO CARDÁPIO*", "━━━━━━━━━━━━", ""]

    for category in snapshot.categories:
        category_items = filter_items_by_category(available_items, category.name)
        if not category_items:
            continue
        lines.append(f"🔸 {category.name}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 Me diga qual categoria você quer explorar!")
    return "\n".join(lines)


def _listar_todos(snapshot: MenuSnapshot, limit: int = MAX_FULL_MENU_ITEMS) -> str:
    """Lista itens do cardápio com limite para evitar output muito grande."""
    available_items = _available_items(snapshot.items)
    if not available_items:
        return "Nenhum item disponível no cardápio no momento."

    lines = ["📋 *CARDÁPIO*", "━━━━━━━━━━━━", ""]
    items_shown = 0
    total_items = len(available_items)

    for category in snapshot.categories:
        if items_shown >= limit:
            break

        category_items = filter_items_by_category(available_items, category.name)
        if not category_items:
            continue

        lines.append(f"🍽️ *{category.name.upper()}*")
        for item in category_items:
            if items_shown >= limit:
                break
            lines.append(f"• {item.name} - {_format_price(item.price)}")
            items_shown += 1
        lines.append("")

    lines.append("━━━━━━━━━━━━")
    if items_shown < total_items:
        lines.append("💡 Para ver mais, me diga qual categoria você quer explorar.")
    else:
        lines.append("💡 Se quiser detalhes de algum item, é só me perguntar!")

    return "\n".join(lines)


@tool
def cardapio_tool(query: str) -> str:
    """
    Consulta o cardápio da Macedos.
    Use para listar categorias, itens por categoria, buscar por termo ou consultar um item específico.
    
    Comandos disponíveis:
    - "listar_categorias" ou "categorias": Lista todas as categorias
    - "resumo": Mostra resumo com categorias e contagem
    - "categoria:NOME": Lista itens de uma categoria específica
    - "buscar:TERMO": Busca itens por termo
    - "item:NOME": Consulta um item específico
    - "todos": Lista itens do cardápio (com limite)
    """
    db = _get_db()
    try:
        snapshot = get_menu_snapshot(db)
        
        if not snapshot or not snapshot.items:
            return "Cardápio não disponível no momento. Por favor, tente novamente mais tarde."
        
        query_lower = query.lower().strip()

        if query_lower in ["listar_categorias", "categorias"]:
            return _listar_categorias(snapshot)
        
        if query_lower == "resumo":
            return _listar_resumo(snapshot)
        
        if query_lower.startswith("categoria:"):
            return _buscar_por_categoria(snapshot, query[10:].strip())
        
        if query_lower.startswith("buscar:"):
            return _buscar_por_termo(snapshot, query[7:].strip())
        
        if query_lower.startswith("item:"):
            return _buscar_item_exato(snapshot, query[5:].strip())
        
        if query_lower == "todos":
            return _listar_todos(snapshot)

        if not query_lower:
            return _listar_resumo(snapshot)

        return _buscar_por_termo(snapshot, query)

    except FileNotFoundError:
        return "Não encontrei o arquivo do cardápio para consulta."
    except Exception as exc:
        return f"Erro ao consultar cardápio: {str(exc)}"
    finally:
        db.close()
