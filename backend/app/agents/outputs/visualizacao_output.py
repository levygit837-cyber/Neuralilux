"""
Visualizacao Output - Formatação de visualização de pedido para WhatsApp.
"""


def format_visualizacao(data: dict) -> str:
    """
    Formata a visualização do pedido atual para exibição no WhatsApp.

    Args:
        data: Dicionário com dados do pedido atual

    Returns:
        Texto formatado da visualização
    """
    itens = data.get("itens", [])
    total = data.get("total", 0)
    qtd = data.get("quantidade_itens", 0)

    if not itens:
        return "🛒 Seu pedido está vazio. Quer ver o cardápio para escolher algo?"

    resultado = "🛒 *SEU PEDIDO ATUAL*\n"
    resultado += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for item in itens:
        qtd_item = item.get("quantidade", 1)
        nome = item.get("nome", "Item")
        preco = item.get("preco_unitario", 0)
        subtotal = item.get("subtotal", preco * qtd_item)
        obs = item.get("observacao", "")

        resultado += f"📌 *{qtd_item}x {nome}*\n"
        resultado += f"   💰 {_fmt_preco(preco)} cada = {_fmt_preco(subtotal)}\n"
        if obs:
            resultado += f"   📝 {obs}\n"
        resultado += "\n"

    resultado += "━━━━━━━━━━━━━━━━━━━━\n"
    resultado += f"💰 *TOTAL: {_fmt_preco(total)}*\n"
    resultado += f"\n📦 {qtd} itens no pedido"
    resultado += "\n\nQuer adicionar mais algo, remover algum item ou finalizar o pedido?"

    return resultado


def _fmt_preco(valor: float) -> str:
    """Formata preço para Real brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")