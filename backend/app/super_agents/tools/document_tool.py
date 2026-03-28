"""
Document Tool - Create documents (PDF, TXT, JSON, Markdown) for the Super Agent.
"""
from typing import Optional
from langchain_core.tools import tool
import json
import base64
import io
import structlog

logger = structlog.get_logger()


@tool
def create_document_tool(
    session_id: str,
    company_id: str,
    filename: str,
    file_type: str,
    content: str,
    description: Optional[str] = None,
) -> str:
    """
    Create a document (PDF, TXT, JSON, or Markdown).

    Args:
        session_id: Current session ID
        company_id: Company ID
        filename: Document filename (without extension)
        file_type: Document type - "pdf", "txt", "json", "markdown"
        content: Document content (text for txt/markdown, JSON string for json, text for pdf)
        description: Optional description of the document

    Returns:
        JSON string with document info including base64 content
    """
    try:
        from app.models.models import SuperAgentDocument
        from app.core.database import get_db

        file_type = file_type.lower()
        valid_types = ["pdf", "txt", "json", "markdown"]

        if file_type not in valid_types:
            return json.dumps({
                "error": f"Invalid file_type: {file_type}. Valid types: {valid_types}"
            })

        # Generate file content based on type
        if file_type == "txt":
            file_bytes = content.encode("utf-8")
            full_filename = f"{filename}.txt"

        elif file_type == "json":
            # Validate JSON
            try:
                json_obj = json.loads(content) if isinstance(content, str) else content
                file_bytes = json.dumps(json_obj, indent=2, ensure_ascii=False).encode("utf-8")
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"Invalid JSON content: {str(e)}"})
            full_filename = f"{filename}.json"

        elif file_type == "markdown":
            file_bytes = content.encode("utf-8")
            full_filename = f"{filename}.md"

        elif file_type == "pdf":
            file_bytes = _create_pdf(content, filename)
            full_filename = f"{filename}.pdf"

        # Encode to base64
        content_base64 = base64.b64encode(file_bytes).decode("utf-8")
        file_size = len(file_bytes)

        # Save to database
        db_gen = get_db()
        db = next(db_gen)

        try:
            doc = SuperAgentDocument(
                session_id=session_id,
                company_id=company_id,
                filename=full_filename,
                file_type=file_type,
                content=content if file_type != "pdf" else None,
                content_base64=content_base64 if file_type == "pdf" else None,
                file_size=file_size,
                description=description,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

            logger.info(
                "Document created",
                document_id=doc.id,
                filename=full_filename,
                file_type=file_type,
                file_size=file_size,
            )

            return json.dumps({
                "success": True,
                "document_id": doc.id,
                "filename": full_filename,
                "file_type": file_type,
                "file_size": file_size,
                "content_base64": content_base64,
                "description": description,
            })

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    except Exception as e:
        logger.error("Failed to create document", error=str(e))
        return json.dumps({"error": str(e)})


def _create_pdf(content: str, title: str) -> bytes:
    """
    Create a simple PDF document from text content.

    Args:
        content: Text content for the PDF
        title: Document title

    Returns:
        PDF bytes
    """
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(10)

        # Content
        pdf.set_font("Helvetica", "", 11)

        # Handle encoding for special characters
        lines = content.split("\n")
        for line in lines:
            try:
                # Try to encode as latin-1, replace unsupported chars
                safe_line = line.encode("latin-1", errors="replace").decode("latin-1")
                pdf.multi_cell(0, 6, safe_line, new_x="LMARGIN", new_y="NEXT")
            except Exception:
                pdf.multi_cell(0, 6, "[Content contains unsupported characters]", new_x="LMARGIN", new_y="NEXT")

        return bytes(pdf.output())

    except ImportError:
        logger.warning("fpdf2 not installed, creating simple text-based PDF")
        # Fallback: create a minimal PDF manually
        return _create_minimal_pdf(content, title)


def _create_minimal_pdf(content: str, title: str) -> bytes:
    """Create a minimal PDF without external dependencies."""
    # Simple PDF structure
    content_lines = content.replace("(", "\\(").replace(")", "\\)").split("\n")
    text_stream = ""
    y_pos = 750

    for line in content_lines[:50]:  # Limit to 50 lines
        if y_pos < 50:
            break
        safe_line = line.encode("ascii", errors="replace").decode("ascii")[:80]
        text_stream += f"BT /F1 10 Tf 50 {y_pos} Td ({safe_line}) Tj ET\n"
        y_pos -= 14

    pdf = f"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length {len(text_stream)}>>stream
{text_stream}
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000{300 + len(text_stream):05d} 00000 n 
trailer<</Size 6/Root 1 0 R>>
startxref
{350 + len(text_stream)}
%%EOF"""
    return pdf.encode("latin-1")