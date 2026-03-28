"""
Teste de integração real do agente WhatsApp com cardápio.
Testa se o modelo está usando as ferramentas corretamente.
"""
import pytest
from app.agents.graph.whatsapp_graph import WhatsAppAgentGraph


@pytest.mark.asyncio
async def test_agent_uses_cardapio_tool_on_menu_request():
    """
    Teste de integração real: verifica se o agente usa a ferramenta de cardápio
    quando o usuário pergunta sobre o menu.
    """
    graph = WhatsAppAgentGraph()
    
    # Simular uma conversa real perguntando sobre o cardápio
    result = await graph.run(
        conversation_id="test_conv_001",
        instance_id="test_instance",
        instance_name="test",
        remote_jid="5511999@s.whatsapp.net",
        contact_name="Cliente Teste",
        message="Quero ver o cardápio"
    )
    
    # Verificar se o agente executou a ferramenta de cardápio
    assert result.get("tool_calls") is not None, "Nenhuma ferramenta foi chamada"
    assert len(result["tool_calls"]) > 0, "Lista de tool_calls está vazia"
    
    # Verificar se a ferramenta cardapio_tool foi usada
    tool_names = [call.get("name") for call in result["tool_calls"]]
    assert "cardapio_tool" in tool_names, f"cardapio_tool não foi usada. Tools usadas: {tool_names}"
    
    # Verificar se a resposta contém conteúdo do cardápio
    response = result.get("response", "")
    assert response, "Resposta está vazia"
    
    # Verificar se a resposta tem formatação adequada (emojis e quebras de linha)
    assert "\n" in response, "Resposta não contém quebras de linha"
    
    # Verificar se contém pelo menos um emoji de formatação
    emojis_esperados = ["📋", "🔸", "🍽️", "💡"]
    tem_emoji = any(emoji in response for emoji in emojis_esperados)
    assert tem_emoji, f"Resposta não contém emojis de formatação. Resposta: {response[:200]}"
    
    print("\n" + "="*80)
    print("TESTE DE INTEGRAÇÃO - CARDÁPIO")
    print("="*80)
    print(f"\nMensagem do usuário: 'Quero ver o cardápio'")
    print(f"\nFerramentas usadas: {tool_names}")
    print(f"\nResposta do agente:\n{response}")
    print("\n" + "="*80)


@pytest.mark.asyncio
async def test_agent_uses_cardapio_tool_on_category_request():
    """
    Teste de integração real: verifica se o agente usa a ferramenta de cardápio
    quando o usuário pergunta sobre uma categoria específica.
    """
    graph = WhatsAppAgentGraph()
    
    # Simular uma conversa real perguntando sobre uma categoria
    result = await graph.run(
        conversation_id="test_conv_002",
        instance_id="test_instance",
        instance_name="test",
        remote_jid="5511999999999@s.whatsapp.net",
        contact_name="Cliente Teste",
        message="Quais pizzas vocês têm?"
    )
    
    # Verificar se o agente executou a ferramenta de cardápio
    assert result.get("tool_calls") is not None, "Nenhuma ferramenta foi chamada"
    assert len(result["tool_calls"]) > 0, "Lista de tool_calls está vazia"
    
    # Verificar se a ferramenta cardapio_tool foi usada
    tool_names = [call.get("name") for call in result["tool_calls"]]
    assert "cardapio_tool" in tool_names, f"cardapio_tool não foi usada. Tools usadas: {tool_names}"
    
    # Verificar se a resposta contém conteúdo
    response = result.get("response", "")
    assert response, "Resposta está vazia"
    
    # Verificar formatação
    assert "\n" in response, "Resposta não contém quebras de linha"
    
    print("\n" + "="*80)
    print("TESTE DE INTEGRAÇÃO - CATEGORIA")
    print("="*80)
    print(f"\nMensagem do usuário: 'Quais pizzas vocês têm?'")
    print(f"\nFerramentas usadas: {tool_names}")
    print(f"\nResposta do agente:\n{response}")
    print("\n" + "="*80)


@pytest.mark.asyncio
async def test_agent_response_formatting():
    """
    Teste de integração real: verifica se a resposta do agente está bem formatada.
    """
    graph = WhatsAppAgentGraph()
    
    result = await graph.run(
        conversation_id="test_conv_003",
        instance_id="test_instance",
        instance_name="test",
        remote_jid="5511999999999@s.whatsapp.net",
        contact_name="Cliente Teste",
        message="Me mostra o menu"
    )
    
    response = result.get("response", "")
    assert response, "Resposta está vazia"
    
    # Verificar se não está muito direto (deve ter mais de uma linha)
    linhas = response.split("\n")
    assert len(linhas) > 1, f"Resposta muito direta, sem quebras de linha adequadas. Resposta: {response}"
    
    # Verificar se tem estrutura visual
    tem_estrutura = any(char in response for char in ["•", "━", "📋", "🔸", "🍽️"])
    assert tem_estrutura, f"Resposta sem estrutura visual adequada. Resposta: {response[:200]}"
    
    print("\n" + "="*80)
    print("TESTE DE INTEGRAÇÃO - FORMATAÇÃO")
    print("="*80)
    print(f"\nMensagem do usuário: 'Me mostra o menu'")
    print(f"\nNúmero de linhas na resposta: {len(linhas)}")
    print(f"\nResposta do agente:\n{response}")
    print("\n" + "="*80)