"""
Teste de integração para o sistema de tipos de agentes.
Verifica se a transição entre agentes, cache e ferramentas funcionam corretamente.
"""
import pytest
from app.services.delivery_zone_service import (
    get_delivery_fee,
    list_active_zones,
    get_all_neighborhoods,
    NeighborhoodNotFoundError,
    NoActiveZonesError,
)
from app.agents.agent_router import route_agent, classify_agent_type, should_use_delivery_tool
from app.agents.state import get_active_agent_type, set_active_agent_type, clear_agent_type_cache


class TestDeliveryZoneService:
    """Testa o serviço de zonas de entrega."""
    
    def test_list_active_zones(self, db):
        """Testa listar zonas ativas."""
        zones = list_active_zones(db)
        assert len(zones) > 0
        assert all("name" in zone for zone in zones)
        assert all("delivery_fee" in zone for zone in zones)
    
    def test_get_delivery_fee_known_neighborhood(self, db):
        """Testa consultar taxa para bairro conhecido."""
        result = get_delivery_fee(db, "Centro", 50.0)
        assert result["fee"] >= 0
        assert result["zone_name"] is not None
        assert result["neighborhood"] == "Centro"
    
    def test_get_delivery_fee_unknown_neighborhood(self, db):
        """Testa consultar taxa para bairro desconhecido."""
        with pytest.raises(NeighborhoodNotFoundError):
            get_delivery_fee(db, "Bairro Inexistente")
    
    def test_get_all_neighborhoods(self, db):
        """Testa listar todos os bairros."""
        neighborhoods = get_all_neighborhoods(db)
        assert isinstance(neighborhoods, list)
        assert len(neighborhoods) > 0


class TestAgentRouter:
    """Testa o roteador de agentes."""
    
    def test_classify_agent_type_sales_to_sales(self):
        """Testa que permanece em sales quando não há trigger de SAC."""
        message = "Quero pedir uma pizza"
        agent_type = classify_agent_type(message, "sales")
        assert agent_type == "sales"
    
    def test_classify_agent_type_sales_to_sac(self):
        """Testa transição de sales para sac com reclamação."""
        message = "Meu pedido chegou errado, quero reclamar"
        agent_type = classify_agent_type(message, "sales")
        assert agent_type == "sac"
    
    def test_classify_agent_type_sac_to_sales(self):
        """Testa transição de sac para sales com pedido."""
        message = "Quero fazer um novo pedido"
        agent_type = classify_agent_type(message, "sac")
        assert agent_type == "sales"
    
    def test_classify_agent_type_sac_stays_sac(self):
        """Testa que permanece em sac quando não há trigger de sales."""
        message = "Meu problema ainda não foi resolvido"
        agent_type = classify_agent_type(message, "sac")
        assert agent_type == "sac"
    
    def test_should_use_delivery_tool(self):
        """Testa detecção de quando usar delivery_tool."""
        assert should_use_delivery_tool("Qual a taxa de entrega?") == True
        assert should_use_delivery_tool("Vocês entregam no Centro?") == True
        assert should_use_delivery_tool("Quero uma pizza") == False
        assert should_use_delivery_tool("Cardápio") == False


class TestAgentTypeCache:
    """Testa o cache de tipos de agentes."""
    
    def test_set_and_get_agent_type(self):
        """Testa definir e obter tipo de agente."""
        conversation_id = "test_conv_123"
        
        # Valor padrão deve ser sales
        assert get_active_agent_type(conversation_id) == "sales"
        
        # Definir como sac
        set_active_agent_type(conversation_id, "sac")
        assert get_active_agent_type(conversation_id) == "sac"
        
        # Definir como sales
        set_active_agent_type(conversation_id, "sales")
        assert get_active_agent_type(conversation_id) == "sales"
        
        # Limpar
        clear_agent_type_cache(conversation_id)
        assert get_active_agent_type(conversation_id) == "sales"
    
    def test_clear_all_cache(self):
        """Testa limpar todo o cache."""
        set_active_agent_type("conv1", "sac")
        set_active_agent_type("conv2", "sac")
        
        clear_agent_type_cache()
        
        assert get_active_agent_type("conv1") == "sales"
        assert get_active_agent_type("conv2") == "sales"


class TestDeliveryTool:
    """Testa a ferramenta de entrega."""
    
    def test_delivery_tool_consultar_taxa(self, db):
        """Testa consultar taxa de entrega."""
        from app.agents.tools.delivery_tool import delivery_tool, set_active_conversation
        
        set_active_conversation("test_conv")
        result = delivery_tool.invoke({
            "acao": "consultar_taxa",
            "bairro": "Centro",
            "valor_pedido": 50.0
        })
        
        assert result is not None
        assert "Taxa de entrega" in result or "taxa" in result.lower()
    
    def test_delivery_tool_listar_regioes(self, db):
        """Testa listar regiões de entrega."""
        from app.agents.tools.delivery_tool import delivery_tool, set_active_conversation
        
        set_active_conversation("test_conv")
        result = delivery_tool.invoke({
            "acao": "listar_regioes"
        })
        
        assert result is not None
        assert "Zonas de Entrega" in result or "zonas" in result.lower()
    
    def test_delivery_tool_listar_bairros(self, db):
        """Testa listar bairros atendidos."""
        from app.agents.tools.delivery_tool import delivery_tool, set_active_conversation
        
        set_active_conversation("test_conv")
        result = delivery_tool.invoke({
            "acao": "listar_bairros"
        })
        
        assert result is not None
        assert "Bairros" in result or "bairros" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
