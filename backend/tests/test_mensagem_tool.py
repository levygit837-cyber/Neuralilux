"""
Testes para a ferramenta de envio de mensagens (mensagem_tool).
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.agents.tools.mensagem_tool import mensagem_tool


class TestMensagemTool:
    """Testa a ferramenta de envio de mensagens."""

    @pytest.mark.asyncio
    async def test_mensagem_tool_success(self):
        """Testa envio de mensagem com sucesso."""
        with patch('app.agents.tools.mensagem_tool.EvolutionAPIService') as mock_evolution_class:
            # Configurar mock
            mock_evolution = MagicMock()
            mock_evolution.send_text_message = AsyncMock(return_value={"key": {"id": "msg-123"}})
            mock_evolution_class.return_value = mock_evolution
            
            result = mensagem_tool.invoke({
                "instance_name": "TestInstance",
                "remote_jid": "5511999999999@s.whatsapp.net",
                "mensagem": "Olá, tudo bem?"
            })
            
            assert "enviada com sucesso" in result.lower()
            assert "5511999999999@s.whatsapp.net" in result
            mock_evolution.send_text_message.assert_called_once_with(
                instance_name="TestInstance",
                remote_jid="5511999999999@s.whatsapp.net",
                text="Olá, tudo bem?"
            )

    @pytest.mark.asyncio
    async def test_mensagem_tool_evolution_api_error(self):
        """Testa erro na Evolution API."""
        with patch('app.agents.tools.mensagem_tool.EvolutionAPIService') as mock_evolution_class:
            mock_evolution = MagicMock()
            mock_evolution.send_text_message = AsyncMock(side_effect=Exception("Connection error"))
            mock_evolution_class.return_value = mock_evolution
            
            result = mensagem_tool.invoke({
                "instance_name": "TestInstance",
                "remote_jid": "5511999999999@s.whatsapp.net",
                "mensagem": "Teste"
            })
            
            assert "Erro ao enviar mensagem" in result
            assert "Connection error" in result

    @pytest.mark.asyncio
    async def test_mensagem_tool_with_empty_message(self):
        """Testa envio de mensagem vazia."""
        with patch('app.agents.tools.mensagem_tool.EvolutionAPIService') as mock_evolution_class:
            mock_evolution = MagicMock()
            mock_evolution.send_text_message = AsyncMock(return_value={"key": {"id": "msg-456"}})
            mock_evolution_class.return_value = mock_evolution
            
            result = mensagem_tool.invoke({
                "instance_name": "TestInstance",
                "remote_jid": "5511999999999@s.whatsapp.net",
                "mensagem": ""
            })
            
            # Deve tentar enviar mesmo com mensagem vazia
            mock_evolution.send_text_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_mensagem_tool_with_long_message(self):
        """Testa envio de mensagem longa."""
        long_message = "A" * 1000
        
        with patch('app.agents.tools.mensagem_tool.EvolutionAPIService') as mock_evolution_class:
            mock_evolution = MagicMock()
            mock_evolution.send_text_message = AsyncMock(return_value={"key": {"id": "msg-789"}})
            mock_evolution_class.return_value = mock_evolution
            
            result = mensagem_tool.invoke({
                "instance_name": "TestInstance",
                "remote_jid": "5511999999999@s.whatsapp.net",
                "mensagem": long_message
            })
            
            assert "enviada com sucesso" in result.lower()
            mock_evolution.send_text_message.assert_called_once_with(
                instance_name="TestInstance",
                remote_jid="5511999999999@s.whatsapp.net",
                text=long_message
            )

    @pytest.mark.asyncio
    async def test_mensagem_tool_with_special_characters(self):
        """Testa envio de mensagem com caracteres especiais."""
        special_message = "Olá! 😊 Como vai? @#$%&*()"
        
        with patch('app.agents.tools.mensagem_tool.EvolutionAPIService') as mock_evolution_class:
            mock_evolution = MagicMock()
            mock_evolution.send_text_message = AsyncMock(return_value={"key": {"id": "msg-special"}})
            mock_evolution_class.return_value = mock_evolution
            
            result = mensagem_tool.invoke({
                "instance_name": "TestInstance",
                "remote_jid": "5511999999999@s.whatsapp.net",
                "mensagem": special_message
            })
            
            assert "enviada com sucesso" in result.lower()
            mock_evolution.send_text_message.assert_called_once_with(
                instance_name="TestInstance",
                remote_jid="5511999999999@s.whatsapp.net",
                text=special_message
            )

    @pytest.mark.asyncio
    async def test_mensagem_tool_parameters_validation(self):
        """Testa que todos os parâmetros são usados."""
        with patch('app.agents.tools.mensagem_tool.EvolutionAPIService') as mock_evolution_class:
            mock_evolution = MagicMock()
            mock_evolution.send_text_message = AsyncMock(return_value={"key": {"id": "msg-params"}})
            mock_evolution_class.return_value = mock_evolution
            
            mensagem_tool.invoke({
                "instance_name": "MyInstance",
                "remote_jid": "5511888888888@s.whatsapp.net",
                "mensagem": "Test message"
            })
            
            # Verificar que todos os parâmetros foram passados corretamente
            call_args = mock_evolution.send_text_message.call_args
            assert call_args[1]["instance_name"] == "MyInstance"
            assert call_args[1]["remote_jid"] == "5511888888888@s.whatsapp.net"
            assert call_args[1]["text"] == "Test message"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
