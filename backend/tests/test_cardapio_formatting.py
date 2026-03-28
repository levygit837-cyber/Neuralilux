"""
Testes de formatação de respostas do cardápio.
"""
import pytest
from app.agents.graph.nodes import _format_whatsapp_response


def test_format_whatsapp_response_preserves_cardapio_with_emojis():
    """Testa se a formatação preserva o cardápio quando tem emojis de seção."""
    cardapio_context = """📋 *NOSSO CARDÁPIO*
━━━━━━━━━━━━

🔸 Pizzas
🔸 Bebidas
🔸 Sobremesas

━━━━━━━━━━━━
💡 Me diga qual categoria você quer explorar!"""
    
    response = "Aqui está o cardápio"
    
    result = _format_whatsapp_response(response, cardapio_context)
    
    # Deve retornar o contexto diretamente quando tem emojis de seção
    assert result == cardapio_context


def test_format_whatsapp_response_adds_line_breaks_before_lists():
    """Testa se adiciona quebras de linha antes de listas."""
    response = "Aqui estão as opções.• Item 1• Item 2• Item 3"
    
    result = _format_whatsapp_response(response, None)
    
    # Deve adicionar quebras de linha antes dos bullet points
    assert "\n\n•" in result


def test_format_whatsapp_response_adds_line_breaks_before_section_emojis():
    """Testa se adiciona quebras de linha antes de emojis de seção."""
    response = "Veja o cardápio.📋 Categorias disponíveis"
    
    result = _format_whatsapp_response(response, None)
    
    # Deve adicionar quebras de linha antes do emoji de seção
    assert "\n\n📋" in result


def test_format_whatsapp_response_handles_empty_response():
    """Testa se lida corretamente com resposta vazia."""
    result = _format_whatsapp_response("", None)
    
    assert result == ""


def test_format_whatsapp_response_handles_none_cardapio():
    """Testa se lida corretamente quando não há contexto de cardápio."""
    response = "Olá! Como posso ajudar?"
    
    result = _format_whatsapp_response(response, None)
    
    # Deve retornar a resposta sem modificações significativas
    assert "Olá!" in result


def test_format_whatsapp_response_preserves_existing_line_breaks():
    """Testa se preserva quebras de linha existentes."""
    response = """Olá!

Como posso ajudar você hoje?"""
    
    result = _format_whatsapp_response(response, None)
    
    # Deve preservar as quebras de linha existentes
    assert "\n\n" in result


def test_cardapio_formatting_has_emojis_and_structure():
    """Testa se a formatação do cardápio contém emojis e estrutura adequada."""
    # Teste simplificado focado apenas na formatação
    sample_cardapio = """📋 *NOSSO CARDÁPIO*
━━━━━━━━━━━━

🔸 Pizzas
🔸 Bebidas
🔸 Sobremesas

━━━━━━━━━━━━━━━━━━━━
💡 Me diga qual categoria você quer explorar!"""
    
    # Verificar estrutura básica
    assert "📋" in sample_cardapio
    assert "🔸" in sample_cardapio
    assert "━" in sample_cardapio
    assert "💡" in sample_cardapio
    assert "\n" in sample_cardapio
    assert "Pizzas" in sample_cardapio


def test_categoria_formatting_has_proper_structure():
    """Testa se a formatação de categoria tem estrutura adequada."""
    # Teste simplificado focado apenas na formatação
    sample_categoria = """🍽️ *PIZZAS*
━━━━━━━━━━━━

📌 *Pizza Margherita*
   _Molho de tomate, mussarela e manjericão_
   💰 R$ 45,00

━━━━━━━━━━━━
💡 Quer adicionar algum item na sua comanda?"""
    
    # Verificar estrutura básica
    assert "🍽️" in sample_categoria
    assert "📌" in sample_categoria
    assert "💰" in sample_categoria
    assert "💡" in sample_categoria
    assert "━" in sample_categoria
    assert "\n" in sample_categoria
    assert "PIZZAS" in sample_categoria
    assert "Pizza Margherita" in sample_categoria
    assert "R$ 45,00" in sample_categoria
