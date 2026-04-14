"""
Testes para validar o funcionamento dos agentes Sales e SAC.
Verifica roteamento, prompts e ferramentas disponíveis.
"""
import pytest
from app.agents.agent_router import route_agent, classify_agent_type
from app.agents.state import get_active_agent_type, set_active_agent_type, clear_agent_type_cache
from app.agents.prompts import SALES_AGENT_PROMPT, SAC_AGENT_PROMPT


class TestSalesSACRouting:
    """Testa o roteamento entre agentes Sales e SAC."""

    def test_sales_keywords_trigger_sac_transition(self):
        """Testa que palavras-chave de SAC disparam transição de Sales para SAC."""
        sac_messages = [
            "Meu pedido chegou errado",
            "Quero reclamar do meu pedido",
            "O pedido está atrasado",
            "Quero cancelar meu pedido",
            "Quero devolução",
            "Item veio estragado",
            "Não chegou nada",
        ]
        
        for message in sac_messages:
            agent_type = classify_agent_type(message, "sales")
            assert agent_type == "sac", f"Mensagem '{message}' deveria transicionar para SAC"

    def test_sac_keywords_trigger_sales_transition(self):
        """Testa que palavras-chave de Sales disparam transição de SAC para Sales."""
        sales_messages = [
            "Quero fazer um novo pedido",
            "Gostaria de pedir uma pizza",
            "Quero ver o cardápio",
            "Vou levar um hambúrguer",
            "Quero adicionar algo",
            "Quanto custa",
        ]
        
        for message in sales_messages:
            agent_type = classify_agent_type(message, "sac")
            assert agent_type == "sales", f"Mensagem '{message}' deveria transicionar para Sales"

    def test_sales_remains_in_sales_without_sac_trigger(self):
        """Testa que Sales permanece em Sales sem trigger de SAC."""
        sales_messages = [
            "Quero uma pizza",
            "Me mostre o cardápio",
            "Qual o preço da pizza?",
            "Adicionar ao pedido",
        ]
        
        for message in sales_messages:
            agent_type = classify_agent_type(message, "sales")
            assert agent_type == "sales", f"Mensagem '{message}' deveria permanecer em Sales"

    def test_sac_remains_in_sac_without_sales_trigger(self):
        """Testa que SAC permanece em SAC sem trigger de Sales."""
        sac_messages = [
            "Meu problema ainda não foi resolvido",
            "Preciso de ajuda com meu pedido",
            "A situação continua a mesma",
            "Não estou satisfeito",
        ]
        
        for message in sac_messages:
            agent_type = classify_agent_type(message, "sac")
            assert agent_type == "sac", f"Mensagem '{message}' deveria permanecer em SAC"


class TestSalesSACPrompts:
    """Testa os prompts específicos para Sales e SAC."""

    def test_sales_prompt_exists(self):
        """Testa que SALES_AGENT_PROMPT existe."""
        assert SALES_AGENT_PROMPT is not None
        assert len(SALES_AGENT_PROMPT) > 0

    def test_sac_prompt_exists(self):
        """Testa que SAC_AGENT_PROMPT existe."""
        assert SAC_AGENT_PROMPT is not None
        assert len(SAC_AGENT_PROMPT) > 0

    def test_sales_prompt_mentions_sales_focus(self):
        """Testa que prompt de Sales menciona foco em vendas."""
        assert "VENDAS" in SALES_AGENT_PROMPT or "vendas" in SALES_AGENT_PROMPT.lower()
        assert "fechar vendas" in SALES_AGENT_PROMPT.lower() or "completar o pedido" in SALES_AGENT_PROMPT.lower()

    def test_sac_prompt_mentions_sac_focus(self):
        """Testa que prompt de SAC menciona foco em suporte."""
        assert "SAC" in SAC_AGENT_PROMPT or "Serviço de Atendimento ao Cliente" in SAC_AGENT_PROMPT
        assert "RESOLUÇÃO DE PROBLEMAS" in SAC_AGENT_PROMPT or "resolução de problemas" in SAC_AGENT_PROMPT.lower()
        assert "empatia" in SAC_AGENT_PROMPT.lower() or "compreensão" in SAC_AGENT_PROMPT.lower()

    def test_sales_prompt_lists_correct_tools(self):
        """Testa que prompt de Sales lista as ferramentas corretas."""
        assert "cardapio_tool" in SALES_AGENT_PROMPT
        assert "pedido_tool" in SALES_AGENT_PROMPT
        assert "delivery_tool" in SALES_AGENT_PROMPT
        assert "horario_tool" in SALES_AGENT_PROMPT

    def test_sac_prompt_lists_correct_tools(self):
        """Testa que prompt de SAC lista as ferramentas corretas."""
        assert "cardapio_tool" in SAC_AGENT_PROMPT
        assert "pedido_tool" in SAC_AGENT_PROMPT
        assert "delivery_tool" in SAC_AGENT_PROMPT
        assert "horario_tool" in SAC_AGENT_PROMPT


class TestSalesSACCache:
    """Testa o cache de tipos de agentes."""

    def test_default_agent_type_is_sales(self):
        """Testa que o tipo padrão é sales."""
        clear_agent_type_cache()
        conversation_id = "test_conv_default"
        assert get_active_agent_type(conversation_id) == "sales"

    def test_set_and_get_sales_type(self):
        """Testa definir e obter tipo sales."""
        conversation_id = "test_conv_sales"
        set_active_agent_type(conversation_id, "sales")
        assert get_active_agent_type(conversation_id) == "sales"

    def test_set_and_get_sac_type(self):
        """Testa definir e obter tipo sac."""
        conversation_id = "test_conv_sac"
        set_active_agent_type(conversation_id, "sac")
        assert get_active_agent_type(conversation_id) == "sac"

    def test_clear_cache_resets_to_sales(self):
        """Testa que limpar cache reseta para sales."""
        conversation_id = "test_conv_clear"
        set_active_agent_type(conversation_id, "sac")
        clear_agent_type_cache(conversation_id)
        assert get_active_agent_type(conversation_id) == "sales"


class TestSalesSACRoutingIntegration:
    """Testes de integração do roteamento Sales/SAC."""

    def test_route_agent_sales_to_sac_transition(self, db):
        """Testa roteamento completo de Sales para SAC."""
        from app.models.models import Conversation, Contact, Instance
        
        # Setup
        conversation = Conversation(
            id="test_conv_1",
            instance_id="test_inst_1",
            contact_id="test_contact_1",
            remote_jid="5511999999999@s.whatsapp.net",
            active_agent_type="sales"
        )
        db.add(conversation)
        db.commit()
        
        result = route_agent(
            conversation_id="test_conv_1",
            message="Meu pedido chegou errado, quero reclamar",
            conversation_db=conversation
        )
        
        assert result["agent_type"] == "sac"
        assert result["transition_occurred"] is True
        assert result["previous_agent_type"] == "sales"
        
        # Cleanup
        db.delete(conversation)
        db.commit()

    def test_route_agent_sac_to_sales_transition(self, db):
        """Testa roteamento completo de SAC para Sales."""
        from app.models.models import Conversation
        
        conversation = Conversation(
            id="test_conv_2",
            instance_id="test_inst_2",
            contact_id="test_contact_2",
            remote_jid="5511888888888@s.whatsapp.net",
            active_agent_type="sac"
        )
        db.add(conversation)
        db.commit()
        
        result = route_agent(
            conversation_id="test_conv_2",
            message="Quero fazer um novo pedido",
            conversation_db=conversation
        )
        
        assert result["agent_type"] == "sales"
        assert result["transition_occurred"] is True
        assert result["previous_agent_type"] == "sac"
        
        # Cleanup
        db.delete(conversation)
        db.commit()

    def test_route_agent_no_transition_when_stay_in_sales(self, db):
        """Testa que não há transição quando permanece em Sales."""
        from app.models.models import Conversation
        
        conversation = Conversation(
            id="test_conv_3",
            instance_id="test_inst_3",
            contact_id="test_contact_3",
            remote_jid="5511777777777@s.whatsapp.net",
            active_agent_type="sales"
        )
        db.add(conversation)
        db.commit()
        
        result = route_agent(
            conversation_id="test_conv_3",
            message="Quero uma pizza",
            conversation_db=conversation
        )
        
        assert result["agent_type"] == "sales"
        assert result["transition_occurred"] is False
        assert result["previous_agent_type"] is None
        
        # Cleanup
        db.delete(conversation)
        db.commit()


class TestSalesSACScenarios:
    """Testa cenários típicos de Sales e SAC."""

    def test_sales_scenario_new_order(self):
        """Testa cenário de novo pedido (Sales)."""
        conversation_id = "test_sales_order"
        set_active_agent_type(conversation_id, "sales")
        
        messages = [
            "Olá",
            "Quero ver o cardápio",
            "Quero uma pizza",
            "Quero adicionar uma bebida",
            "Qual o total?",
        ]
        
        for message in messages:
            agent_type = classify_agent_type(message, get_active_agent_type(conversation_id))
            assert agent_type == "sales", f"Mensagem '{message}' deveria permanecer em Sales"
        
        clear_agent_type_cache(conversation_id)

    def test_sac_scenario_complaint(self):
        """Testa cenário de reclamação (SAC)."""
        conversation_id = "test_sac_complaint"
        set_active_agent_type(conversation_id, "sac")
        
        messages = [
            "Meu pedido está atrasado",
            "Já passou 2 horas",
            "Quero cancelar",
        ]
        
        for message in messages:
            agent_type = classify_agent_type(message, get_active_agent_type(conversation_id))
            assert agent_type == "sac", f"Mensagem '{message}' deveria permanecer em SAC"
        
        clear_agent_type_cache(conversation_id)

    def test_transition_sac_to_sales_after_resolution(self):
        """Testa transição de SAC para Sales após resolução."""
        conversation_id = "test_transition"
        set_active_agent_type(conversation_id, "sac")
        
        # Cliente reclama
        agent_type = classify_agent_type("Meu pedido chegou errado", get_active_agent_type(conversation_id))
        assert agent_type == "sac"
        
        # Após resolução, cliente quer novo pedido
        agent_type = classify_agent_type("Quero fazer um novo pedido", get_active_agent_type(conversation_id))
        assert agent_type == "sales"
        
        clear_agent_type_cache(conversation_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
