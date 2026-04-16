"""PDF document processing for RAG."""
from typing import Optional, Union
import structlog
from io import BytesIO

logger = structlog.get_logger()


def extract_text_from_pdf(
    file_content: Union[bytes, BytesIO],
    filename: Optional[str] = None,
) -> str:
    """Extract text from a PDF file.

    Args:
        file_content: PDF file content as bytes or BytesIO
        filename: Optional filename for logging

    Returns:
        Extracted text content
    """
    try:
        from pypdf import PdfReader

        if isinstance(file_content, bytes):
            file_content = BytesIO(file_content)

        reader = PdfReader(file_content)
        text_parts = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_parts.append(text)

        full_text = "\n\n".join(text_parts)
        logger.info(
            "PDF extracted",
            filename=filename,
            page_count=len(reader.pages),
            text_length=len(full_text),
        )
        return full_text

    except Exception as e:
        logger.error("PDF extraction failed", filename=filename, error=str(e))
        return f"[Erro ao extrair PDF: {str(e)}]"


def extract_text_from_pdf_url(url: str) -> Optional[str]:
    """Download and extract text from a PDF URL.

    Args:
        url: URL to the PDF file

    Returns:
        Extracted text or None on failure
    """
    import httpx
    import asyncio

    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        return extract_text_from_pdf(response.content, filename=url)
    except Exception as e:
        logger.error("PDF URL extraction failed", url=url, error=str(e))
        return None


async def extract_text_from_pdf_async(
    file_content: Union[bytes, BytesIO],
    filename: Optional[str] = None,
) -> str:
    """Async wrapper for PDF extraction."""
    return extract_text_from_pdf(file_content, filename)
