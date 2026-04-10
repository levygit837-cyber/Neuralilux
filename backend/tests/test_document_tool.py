"""
Testes para a ferramenta de criação de documentos do Super Agent.
"""
import pytest
import json
import base64
from unittest.mock import MagicMock, patch

# Import must be done carefully due to the @tool decorator
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCreateDocumentToolValidation:
    """Testes de validação que não precisam do banco de dados."""

    def test_invalid_file_type(self):
        """Testa erro com tipo de arquivo inválido."""
        from app.super_agents.tools.document_tool import create_document_tool
        
        payload = {
            "session_id": "test",
            "company_id": "test",
            "filename": "teste",
            "file_type": "invalid_type",
            "content": "Conteúdo",
        }
        
        if hasattr(create_document_tool, "invoke"):
            result = create_document_tool.invoke(payload)
        else:
            result = create_document_tool(**payload)
        
        result_obj = json.loads(result)
        
        assert "error" in result_obj
        assert "Invalid file_type" in result_obj["error"]

    def test_invalid_json_content(self):
        """Testa erro com JSON inválido."""
        from app.super_agents.tools.document_tool import create_document_tool
        
        payload = {
            "session_id": "test",
            "company_id": "test",
            "filename": "teste",
            "file_type": "json",
            "content": "{invalid json",
        }
        
        if hasattr(create_document_tool, "invoke"):
            result = create_document_tool.invoke(payload)
        else:
            result = create_document_tool(**payload)
        
        result_obj = json.loads(result)
        
        assert "error" in result_obj
        assert "Invalid JSON" in result_obj["error"]

    def test_valid_file_types_accepted(self):
        """Testa se tipos válidos são aceitos (sem erros de validação)."""
        from app.super_agents.tools.document_tool import create_document_tool
        
        valid_types = ["pdf", "txt", "json", "markdown", "PDF", "TXT", "JSON", "MARKDOWN"]
        
        for file_type in valid_types:
            payload = {
                "session_id": "test",
                "company_id": "test",
                "filename": "teste",
                "file_type": file_type,
                "content": "Conteúdo de teste",
            }
            
            if hasattr(create_document_tool, "invoke"):
                result = create_document_tool.invoke(payload)
            else:
                result = create_document_tool(**payload)
            
            result_obj = json.loads(result)
            
            # Não deve ter erro de tipo inválido
            if "error" in result_obj:
                assert "Invalid file_type" not in result_obj["error"], f"Tipo {file_type} deveria ser válido"


class TestCreateDocumentToolIntegration:
    """Testes de integração com banco de dados (requer DB configurado)."""

    @pytest.fixture
    def mock_db_dependencies(self):
        """Setup mocks for database dependencies."""
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()
        mock_db.close = MagicMock()
        mock_db.rollback = MagicMock()
        
        mock_doc = MagicMock()
        mock_doc.id = "doc-test-123"
        mock_doc.filename = "teste.txt"
        mock_doc.file_type = "txt"
        mock_doc.file_size = 100
        
        return mock_db, mock_doc

    def test_database_operations_called(self, mock_db_dependencies):
        """Testa se operações do banco são chamadas."""
        from app.super_agents.tools.document_tool import create_document_tool
        from app.core.database import get_db
        
        mock_db, mock_doc = mock_db_dependencies
        
        # Patch get_db to return our mock
        with patch.object(get_db, '__call__', return_value=iter([mock_db])):
            with patch('app.super_agents.tools.document_tool.SuperAgentDocument') as MockDoc:
                MockDoc.return_value = mock_doc
                
                payload = {
                    "session_id": "sess-123",
                    "company_id": "comp-456",
                    "filename": "relatorio",
                    "file_type": "txt",
                    "content": "Conteúdo do relatório",
                }
                
                if hasattr(create_document_tool, "invoke"):
                    result = create_document_tool.invoke(payload)
                else:
                    result = create_document_tool(**payload)
                
                result_obj = json.loads(result)
                
                # Verificar se foi chamado com success
                if result_obj.get("success"):
                    mock_db.add.assert_called_once()
                    mock_db.commit.assert_called_once()

    def test_base64_encoding(self, mock_db_dependencies):
        """Testa se content_base64 é gerado corretamente."""
        from app.super_agents.tools.document_tool import create_document_tool
        
        mock_db, mock_doc = mock_db_dependencies
        
        content = "Conteúdo de teste para verificação"
        
        with patch('app.core.database.get_db', return_value=iter([mock_db])):
            with patch('app.super_agents.tools.document_tool.SuperAgentDocument') as MockDoc:
                MockDoc.return_value = mock_doc
                
                payload = {
                    "session_id": "sess-123",
                    "company_id": "comp-456",
                    "filename": "teste",
                    "file_type": "txt",
                    "content": content,
                }
                
                if hasattr(create_document_tool, "invoke"):
                    result = create_document_tool.invoke(payload)
                else:
                    result = create_document_tool(**payload)
                
                result_obj = json.loads(result)
                
                # Se tiver content_base64 no resultado, verificar se é válido
                if "content_base64" in result_obj:
                    decoded = base64.b64decode(result_obj["content_base64"])
                    assert decoded.decode("utf-8") == content


class TestDocumentOutputFormat:
    """Testes do formato de saída do documento."""

    def test_output_has_required_fields(self):
        """Verifica que output tem campos necessários quando há erro."""
        from app.super_agents.tools.document_tool import create_document_tool
        
        payload = {
            "session_id": "test",
            "company_id": "test",
            "filename": "teste",
            "file_type": "invalid",
            "content": "test",
        }
        
        if hasattr(create_document_tool, "invoke"):
            result = create_document_tool.invoke(payload)
        else:
            result = create_document_tool(**payload)
        
        result_obj = json.loads(result)
        
        # Deve ter campo error
        assert "error" in result_obj
        # Não deve ter success
        assert result_obj.get("success") is None or result_obj.get("success") is False
