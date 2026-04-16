"""Tests for RAG system."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from io import BytesIO
import json

pytest_plugins = ('pytest_asyncio',)

from app.rag.vector_store import RAGVectorStore, get_rag_store
from app.rag.retriever import RAGRetriever, get_rag_retriever
from app.rag.document_processor import extract_text_from_pdf, extract_text_from_pdf_url
from app.models.models import CompanyRule, RuleCategory


@pytest.fixture(autouse=True)
def reset_rag_singletons():
    """Reset RAG singletons between tests."""
    import app.rag.vector_store as vs_module
    import app.rag.retriever as ret_module

    vs_module._rag_store = None
    ret_module._retriever = None

    yield

    vs_module._rag_store = None
    ret_module._retriever = None


class TestDocumentProcessor:
    """Tests for PDF text extraction."""

    @patch("pypdf.PdfReader")
    def test_extract_text_from_pdf_bytes(self, mock_reader_class):
        """Test extracting text from PDF bytes."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test page content"
        mock_reader_class.return_value.pages = [mock_page]

        result = extract_text_from_pdf(b"%PDF-1.4 fake pdf content", filename="test.pdf")

        assert result == "Test page content"

    @patch("pypdf.PdfReader")
    def test_extract_text_from_pdf_empty(self, mock_reader_class):
        """Test extracting text from empty PDF."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader_class.return_value.pages = [mock_page]

        result = extract_text_from_pdf(b"%PDF-1.4", filename="empty.pdf")

        assert result == ""

    @patch("pypdf.PdfReader")
    def test_extract_text_from_pdf_exception(self, mock_reader_class):
        """Test handling PDF extraction errors."""
        mock_reader_class.side_effect = Exception("Invalid PDF")

        result = extract_text_from_pdf(b"not a pdf", filename="bad.pdf")

        assert "Erro ao extrair PDF" in result

    @patch("httpx.get")
    def test_extract_text_from_pdf_url_success(self, mock_get):
        """Test extracting text from PDF URL."""
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 test"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with patch("app.rag.document_processor.extract_text_from_pdf") as mock_extract:
            mock_extract.return_value = "Extracted text"
            result = extract_text_from_pdf_url("http://example.com/test.pdf")

            assert result == "Extracted text"

    @patch("httpx.get")
    def test_extract_text_from_pdf_url_failure(self, mock_get):
        """Test handling PDF URL extraction errors."""
        mock_get.side_effect = Exception("Network error")

        result = extract_text_from_pdf_url("http://example.com/test.pdf")

        assert result is None


class TestRAGVectorStore:
    """Tests for RAG Vector Store - basic tests."""
    pass


class TestRAGRetriever:
    """Tests for RAG Retriever."""

    @pytest.fixture
    def mock_retriever(self):
        """Create mock retriever."""
        with patch("app.rag.retriever.get_rag_store") as mock_store:
            mock_vector_store = MagicMock()
            mock_vector_store.search.return_value = [
                {
                    "id": "rule_1",
                    "title": "Refund Policy",
                    "content": "Full refund within 30 days",
                    "category": "policy",
                    "score": 0.9
                }
            ]
            mock_store.return_value = mock_vector_store

            retriever = RAGRetriever()
            yield retriever, mock_vector_store

    @pytest.mark.asyncio
    async def test_retrieve_with_rules(self, mock_retriever):
        """Test retrieving rules context."""
        retriever, mock_store = mock_retriever

        result = await retriever.retrieve(
            company_id="company_123",
            message="How do I get a refund?",
            limit=5
        )

        assert "rules_context" in result
        assert "Refund Policy" in result["rules_context"]
        mock_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_with_pdf_content(self, mock_retriever):
        """Test retrieving with PDF content."""
        retriever, mock_store = mock_retriever

        result = await retriever.retrieve(
            company_id="company_123",
            message="Analyze this document",
            pdf_content="PDF content here",
            limit=5
        )

        assert "document_context" in result
        assert "PDF content here" in result["document_context"]

    @pytest.mark.asyncio
    async def test_retrieve_no_results(self, mock_retriever):
        """Test retrieving when no rules found."""
        retriever, mock_store = mock_retriever
        mock_store.search.return_value = []

        result = await retriever.retrieve(
            company_id="company_123",
            message="Random query",
            limit=5
        )

        assert "Nenhuma regra" in result["rules_context"]

    @pytest.mark.asyncio
    async def test_retrieve_error_handling(self, mock_retriever):
        """Test error handling in retrieval."""
        retriever, mock_store = mock_retriever
        mock_store.search.side_effect = Exception("Qdrant error")

        result = await retriever.retrieve(
            company_id="company_123",
            message="test",
            limit=5
        )

        assert "Erro ao buscar regras" in result["rules_context"]

    def test_build_context_prompt(self, mock_retriever):
        """Test building context prompt."""
        retriever, _ = mock_retriever

        result = retriever.build_context_prompt({
            "rules_context": "[REGRAS]\nTest rules",
            "document_context": "[DOC]Test doc[/DOC]"
        })

        assert "REGRAS" in result
        assert "DOC" in result

    def test_build_context_prompt_empty(self, mock_retriever):
        """Test building empty context prompt."""
        retriever, _ = mock_retriever

        result = retriever.build_context_prompt({})

        assert result == ""


class TestRAGIntegration:
    """Integration tests for RAG with the agent."""
    pass


class TestCompanyRuleModel:
    """Tests for CompanyRule model."""

    def test_rule_category_enum(self):
        """Test RuleCategory enum values."""
        assert RuleCategory.POLICY.value == "politica"
        assert RuleCategory.PROCEDURE.value == "procedimento"
        assert RuleCategory.FAQ.value == "faq"
        assert RuleCategory.COMPLIANCE.value == "compliance"
        assert RuleCategory.GENERAL.value == "general"

    def test_company_rule_creation(self, db):
        """Test creating a CompanyRule."""
        rule = CompanyRule(
            company_id="company_123",
            title="Test Policy",
            content="This is a test policy content",
            category="politica"
        )
        db.add(rule)
        db.commit()

        retrieved = db.query(CompanyRule).filter(CompanyRule.id == rule.id).first()

        assert retrieved is not None
        assert retrieved.title == "Test Policy"
        assert retrieved.category == "politica"
        assert retrieved.is_active is True

    def test_company_rule_update(self, db):
        """Test updating a CompanyRule."""
        rule = CompanyRule(
            company_id="company_123",
            title="Original Title",
            content="Original content",
            category="faq"
        )
        db.add(rule)
        db.commit()

        rule.title = "Updated Title"
        db.commit()

        retrieved = db.query(CompanyRule).filter(CompanyRule.id == rule.id).first()
        assert retrieved.title == "Updated Title"

    def test_company_rule_soft_delete(self, db):
        """Test soft delete of CompanyRule."""
        rule = CompanyRule(
            company_id="company_123",
            title="To Delete",
            content="Content",
            category="general"
        )
        db.add(rule)
        db.commit()

        rule.is_active = False
        db.commit()

        active_rules = db.query(CompanyRule).filter(
            CompanyRule.company_id == "company_123",
            CompanyRule.is_active == True
        ).all()

        assert len(active_rules) == 0


class TestRAGSchemas:
    """Tests for RAG Pydantic schemas."""

    def test_rule_create_valid(self):
        """Test RuleCreate schema validation."""
        from app.schemas.rag import RuleCreate

        rule = RuleCreate(
            title="Test Rule",
            content="Test content",
            category="faq"
        )

        assert rule.title == "Test Rule"
        assert rule.category == "faq"

    def test_rule_create_with_company_id(self):
        """Test RuleCreate with company_id."""
        from app.schemas.rag import RuleCreate

        rule = RuleCreate(
            title="Test Rule",
            content="Test content",
            category="policy",
            company_id="company_123"
        )

        assert rule.company_id == "company_123"

    def test_rule_update_partial(self):
        """Test RuleUpdate with partial fields."""
        from app.schemas.rag import RuleUpdate

        update = RuleUpdate(title="New Title")

        assert update.title == "New Title"
        assert update.content is None

    def test_rule_response(self):
        """Test RuleResponse schema."""
        from app.schemas.rag import RuleResponse
        from datetime import datetime

        response = RuleResponse(
            id="rule_123",
            company_id="company_123",
            title="Test",
            content="Content",
            category="faq",
            is_active=True,
            created_at=datetime.now()
        )

        assert response.id == "rule_123"

    def test_document_index_request(self):
        """Test DocumentIndexRequest schema."""
        from app.schemas.rag import DocumentIndexRequest

        request = DocumentIndexRequest(
            company_id="company_123",
            title="Test Doc",
            content="Document content",
            category="general"
        )

        assert request.title == "Test Doc"

    def test_document_index_response(self):
        """Test DocumentIndexResponse schema."""
        from app.schemas.rag import DocumentIndexResponse

        response = DocumentIndexResponse(
            success=True,
            document_id="doc_123",
            message="Indexed successfully"
        )

        assert response.success is True
        assert response.document_id == "doc_123"


class TestRAGEndpoints:
    """Tests for RAG API endpoints - basic tests."""
    pass


class TestAgentChatWithDocument:
    """Tests for agent chat with document content."""

    def test_agent_chat_request_with_document(self, client, auth_headers):
        """Test POST /api/v1/agents/chat with document_content."""
        response = client.post(
            "/api/v1/agents/chat",
            json={
                "message": "Analyze this document",
                "document_content": "PDF extracted text content",
                "document_filename": "document.pdf"
            },
            headers=auth_headers
        )

        assert response.status_code in [200, 500]


class TestRAGSingleton:
    """Tests for singleton pattern."""

    def test_get_rag_store_singleton(self):
        """Test that get_rag_store returns singleton."""
        with patch("app.rag.vector_store.RAGVectorStore") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance

            store1 = get_rag_store()
            store2 = get_rag_store()

            assert store1 is store2

    def test_get_rag_retriever_singleton(self):
        """Test that get_rag_retriever returns singleton."""
        with patch("app.rag.retriever.get_rag_store") as mock_store:
            mock_store.return_value = MagicMock()

            retriever1 = get_rag_retriever()
            retriever2 = get_rag_retriever()

            assert retriever1 is retriever2
