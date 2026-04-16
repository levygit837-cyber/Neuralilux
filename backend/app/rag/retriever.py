"""RAG retriever for agent context injection."""
from typing import List, Dict, Any, Optional
import structlog
from app.rag.vector_store import get_rag_store
from app.rag.document_processor import extract_text_from_pdf

logger = structlog.get_logger()


class RAGRetriever:
    """Retrieves relevant context for the agent."""

    def __init__(self):
        self.vector_store = get_rag_store()

    async def retrieve(
        self,
        company_id: str,
        message: str,
        pdf_content: Optional[str] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Retrieve relevant context for the agent.

        Args:
            company_id: Company ID for filtering rules
            message: User message to search for relevant rules
            pdf_content: Optional extracted PDF text
            limit: Maximum number of rules to retrieve

        Returns:
            Dict with 'rules' and 'document' context
        """
        rules_context = ""
        document_context = ""

        try:
            rules = self.vector_store.search(
                query=message,
                company_id=company_id,
                limit=limit,
            )

            if rules:
                rules_lines = ["[REGRAS DE NEGÓCIO]"]
                for idx, rule in enumerate(rules, 1):
                    rules_lines.append(f"\n--- Regra {idx}: {rule['title']} ({rule['category']}) ---")
                    rules_lines.append(rule['content'])
                rules_context = "\n".join(rules_lines)
                logger.info(
                    "Retrieved rules",
                    company_id=company_id,
                    count=len(rules),
                    message_preview=message[:50],
                )
            else:
                rules_context = "[Nenhuma regra de negócio encontrada]"

        except Exception as e:
            logger.error("RAG retrieval failed", company_id=company_id, error=str(e))
            rules_context = f"[Erro ao buscar regras: {str(e)}]"

        if pdf_content:
            document_context = f"[DOCUMENTO DO CLIENTE]\n{pdf_content}\n[/DOCUMENTO]"
            logger.info("PDF content attached", company_id=company_id, text_length=len(pdf_content))

        return {
            "rules_context": rules_context,
            "document_context": document_context,
            "rules_found": len(rules) if 'rules' in dir() else 0,
        }

    def build_context_prompt(self, retrieval_result: Dict[str, Any]) -> str:
        """Build the context string to inject into the agent's prompt."""
        parts = []

        if retrieval_result.get("rules_context"):
            parts.append(retrieval_result["rules_context"])

        if retrieval_result.get("document_context"):
            parts.append(retrieval_result["document_context"])

        if parts:
            return "\n\n".join(parts)
        return ""


_retriever: Optional[RAGRetriever] = None


def get_rag_retriever() -> RAGRetriever:
    """Get singleton RAG retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever
