"""RAG rules API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import CompanyRule, Company
from app.schemas.rag import (
    RuleCreate,
    RuleUpdate,
    RuleResponse,
    RuleListResponse,
    DocumentIndexRequest,
    DocumentIndexResponse,
)
from app.api.v1.endpoints.auth import get_current_user
from app.models.models import User
from app.rag.vector_store import get_rag_store
from app.rag.document_processor import extract_text_from_pdf
import structlog

logger = structlog.get_logger()
router = APIRouter(tags=["RAG"])


@router.post("/rules", response_model=RuleResponse)
async def create_rule(
    rule: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new company rule."""
    company_id = rule.company_id or str(current_user.company_id)

    db_rule = CompanyRule(
        company_id=company_id,
        title=rule.title,
        content=rule.content,
        category=rule.category,
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)

    vector_store = get_rag_store()
    vector_store.add_documents(
        documents=[{
            "id": db_rule.id,
            "title": db_rule.title,
            "content": db_rule.content,
            "category": db_rule.category,
        }],
        company_id=company_id,
    )

    logger.info("Rule created", rule_id=db_rule.id, company_id=company_id)
    return db_rule


@router.get("/rules", response_model=RuleListResponse)
async def list_rules(
    company_id: str = None,
    category: str = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List company rules."""
    company_id = company_id or str(current_user.company_id)

    query = db.query(CompanyRule).filter(CompanyRule.company_id == company_id)

    if category:
        query = query.filter(CompanyRule.category == category)

    if active_only:
        query = query.filter(CompanyRule.is_active == True)

    rules = query.order_by(CompanyRule.created_at.desc()).all()
    return RuleListResponse(rules=rules, total=len(rules))


@router.get("/rules/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific rule."""
    rule = db.query(CompanyRule).filter(CompanyRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if str(rule.company_id) != str(current_user.company_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    return rule


@router.put("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    rule_update: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a rule."""
    db_rule = db.query(CompanyRule).filter(CompanyRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if str(db_rule.company_id) != str(current_user.company_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = rule_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_rule, field, value)

    db.commit()
    db.refresh(db_rule)

    vector_store = get_rag_store()
    vector_store.delete_by_id(f"{db_rule.company_id}_{db_rule.id}")
    vector_store.add_documents(
        documents=[{
            "id": db_rule.id,
            "title": db_rule.title,
            "content": db_rule.content,
            "category": db_rule.category,
        }],
        company_id=str(db_rule.company_id),
    )

    logger.info("Rule updated", rule_id=db_rule.id)
    return db_rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a rule."""
    db_rule = db.query(CompanyRule).filter(CompanyRule.id == rule_id).first()
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if str(db_rule.company_id) != str(current_user.company_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    vector_store = get_rag_store()
    vector_store.delete_by_id(f"{db_rule.company_id}_{db_rule.id}")

    db.delete(db_rule)
    db.commit()

    logger.info("Rule deleted", rule_id=rule_id)
    return {"success": True, "message": "Rule deleted"}


@router.post("/documents/index", response_model=DocumentIndexResponse)
async def index_document(
    request: DocumentIndexRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Index a document into the vector store."""
    company_id = request.company_id or str(current_user.company_id)

    vector_store = get_rag_store()
    doc_id = f"doc_{company_id}_{hash(request.title) % 100000}"

    vector_store.add_documents(
        documents=[{
            "id": doc_id,
            "title": request.title,
            "content": request.content,
            "category": request.category,
        }],
        company_id=company_id,
    )

    logger.info("Document indexed", doc_id=doc_id, company_id=company_id)
    return DocumentIndexResponse(
        success=True,
        document_id=doc_id,
        message="Document indexed successfully",
    )


@router.post("/documents/extract")
async def extract_pdf_text(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Extract text from an uploaded PDF file."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = await file.read()
        text = extract_text_from_pdf(content, filename=file.filename)

        return JSONResponse({
            "success": True,
            "filename": file.filename,
            "text": text,
            "text_length": len(text),
        })
    except Exception as e:
        logger.error("PDF extraction failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to extract PDF: {str(e)}")
