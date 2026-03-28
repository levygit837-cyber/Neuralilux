"""
Pedido Output - Formatação de comanda de pedido para WhatsApp.
"""


def format_comanda(data: dict) -> str:
    """
    Formata uma comanda de pedido para exibição no WhatsApp.

    Args:
        data: Dicionário com dados do pedido

    Returns:
        Texto formatado da comanda
    """
    numero = data.get("numero_pedido", "N/A")
    itens = data.get("itens", [])
    total = data.get("total", 0)
    cliente = data.get("cliente_nome", "")
    endereco = data.get("cliente_endereco", "")
    telefone = data.get("cliente_telefone", "")
    pagamento = data.get("forma_pagamento", "")

    resultado = f"🧾 *COMANDA - Pedido #{numero}*\n"
    resultado += "━━━━━━━━━━━━━━━━━━━━\n\n"

    for item in itens:
        qtd = item.get("quantidade", 1)
        nome = item.get("nome", "Item")
        preco = item.get("preco_unitario", 0)
        subtotal = item.get("subtotal", preco * qtd)
        obs = item.get("observacao", "")

        resultado += f"📦 {qtd}x {nome}..... {_fmt_preco(subtotal)}\n"
        if obs:
            resultado += f"   📝 {obs}\n"

    resultado += "\n━━━━━━━━━━━━━━━━━━━━\n"
    resultado += f"💰 *TOTAL: {_fmt_preco(total)}*\n"

    if cliente:
        resultado += f"\n👤 Cliente: {cliente}"
    if endereco:
        resultado += f"\n📍 Endereço: {endereco}"
    if telefone:
        resultado += f"\n📞 Telefone: {telefone}"
    if pagamento:
        resultado += f"\n💳 Pagamento: {pagamento}"

    return resultado


def _fmt_preco(valor: float) -> str:
    """Formata preço para Real brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")