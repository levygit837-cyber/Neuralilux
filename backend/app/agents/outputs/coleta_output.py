"""
Coleta Output - Formatação de coleta de informações para WhatsApp.
"""


def format_coleta(data: dict) -> str:
    """
    Formata a mensagem de coleta de informações para exibição no WhatsApp.

    Args:
        data: Dicionário com dados da coleta

    Returns:
        Texto formatado da coleta
    """
    etapa = data.get("etapa", "")
    mensagem = data.get("mensagem", "")
    dados_coletados = data.get("dados_coletados", {})
    proxima = data.get("proxima_etapa", "")

    resultado = ""

    # Mostrar o que já foi coletado
    if dados_coletados:
        resultado += "📋 *Dados confirmados:*\n"
        if dados_coletados.get("nome"):
            resultado += f"  👤 Nome: {dados_coletados['nome']}\n"
        if dados_coletados.get("endereco"):
            resultado += f"  📍 Endereço: {dados_coletados['endereco']}\n"
        if dados_coletados.get("telefone"):
            resultado += f"  📞 Telefone: {dados_coletados['telefone']}\n"
        if dados_coletados.get("pagamento"):
            resultado += f"  💳 Pagamento: {dados_coletados['pagamento']}\n"
        resultado += "\n"

    # Mensagem principal
    resultado += mensagem

    # Indicar progresso
    etapas = ["nome", "endereco", "telefone", "pagamento", "confirmacao"]
    if etapa in etapas:
        idx = etapas.index(etapa)
        progresso = "█" * (idx + 1) + "░" * (len(etapas) - idx - 1)
        resultado += f"\n\n📊 Progresso: [{progresso}] {idx + 1}/{len(etapas)}"

    return resultado