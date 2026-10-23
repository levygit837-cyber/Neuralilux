"""Conversão do texto do modelo (markdown) para a formatação do WhatsApp."""

from app.agent.formatting import to_whatsapp


def test_valor_monetario_fica_intacto():
    text = "O total ficou R$ 1.250,00. Taxa de entrega: R$ 8,50!"

    assert to_whatsapp(text) == "O total ficou R$ 1.250,00. Taxa de entrega: R$ 8,50!"


def test_valor_monetario_dentro_de_negrito():
    assert to_whatsapp("Total: **R$ 1.250,00**") == "Total: *R$ 1.250,00*"


def test_negrito_markdown_vira_negrito_whatsapp():
    assert to_whatsapp("Temos **Pizza Toscana** hoje") == "Temos *Pizza Toscana* hoje"


def test_italico_e_tachado():
    assert to_whatsapp("__promo__ e ~~R$ 50,00~~") == "_promo_ e ~R$ 50,00~"


def test_titulo_vira_negrito():
    assert to_whatsapp("## Cardápio\nPizzas") == "*Cardápio*\nPizzas"


def test_lista_markdown_vira_bullet():
    text = "Opções:\n- Pizza Toscana R$ 45,90\n* Calabresa R$ 39,90"

    assert to_whatsapp(text) == "Opções:\n• Pizza Toscana R$ 45,90\n• Calabresa R$ 39,90"


def test_lista_numerada_preservada():
    text = "1. Escolha o item\n2. Informe o endereço"

    assert to_whatsapp(text) == text


def test_link_markdown_vira_texto_e_url():
    assert to_whatsapp("Veja [o cardápio](https://ex.com/c)") == "Veja o cardápio (https://ex.com/c)"


def test_espacos_e_linhas_em_branco_excedentes():
    assert to_whatsapp("  Oi!\n\n\n\nTudo bem?  ") == "Oi!\n\nTudo bem?"
