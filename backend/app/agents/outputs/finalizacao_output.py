"""
Finalizacao Output - Formatação de finalização de pedido para WhatsApp.
"""


def format_finalizacao(data: dict) -> str:
    """
    Formata a confirmação de finalização de pedido para exibição no WhatsApp.

    Args:
        data: Dicionário com dados do pedido finalizado

    Returns:
        Texto formatado da confirmação
    """
    numero = data.get("numero_pedido", "N/A")
    itens = data.get("itens", [])
    total = data.get("total", 0)
    cliente = data.get("cliente_nome", "")
    endereco = data.get("cliente_endereco", "")
    telefone = data.get("cliente_telefone", "")
    pagamento = data.get("forma_pagamento", "")
    tempo = data.get("tempo_estimado", "30-45 minutos")
    mensagem = data.get("mensagem_confirmacao", "")

    resultado = "🎉 *PEDIDO CONFIRMADO!*\n"
    resultado += "━━━━━━━━━━━━━━━━━━━━\n\n"
    resultado += f"📋 Pedido #{numero}\n\n"

    resultado += "*Itens do pedido:*\n"
    for item in itens:
        qtd = item.get("quantidade", 1)
        nome = item.get("nome", "Item")
        subtotal = item.get("subtotal", 0)
        obs = item.get("observacao", "")

        resultado += f"  ✅ {qtd}x {nome} - {_fmt_preco(subtotal)}\n"
        if obs:
            resultado += f"     📝 {obs}\n"

    resultado += f"\n💰 *TOTAL: {_fmt_preco(total)}*\n"
    resultado += f"💳 Pagamento: {pagamento}\n\n"

    resultado += "*Dados de entrega:*\n"
    resultado += f"  👤 {cliente}\n"
    resultado += f"  📍 {endereco}\n"
    resultado += f"  📞 {telefone}\n\n"

    resultado += f"⏰ *Tempo estimado: {tempo}*\n\n"

    if mensagem:
        resultado += f"💬 {mensagem}\n\n"

    resultado += "Obrigado pela preferência! 😊🍕\n"
    resultado += "━━━━━━━━━━━━━━━━━━━━"

    return resultado


def _fmt_preco(valor: float) -> str:
    """Formata preço para Real brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")