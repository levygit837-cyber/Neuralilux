"""Helpers to resolve company and user context for the Super Agent."""
from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy.orm import Session


def run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def resolve_agent_chat_actor(
    db: Session,
    company_id: Optional[str],
    user_id: Optional[str],
    session_id: Optional[str] = None,
) -> tuple[str, str]:
    from app.models.models import Company, User
    from app.super_agents.memory.session_memory import SessionMemory

    if session_id:
        session_info = run_sync(SessionMemory.get_session(db=db, session_id=session_id))
        if session_info:
            return str(session_info["company_id"]), str(session_info["user_id"])

    resolved_company_id = company_id or ""
    resolved_user_id = user_id or ""

    if resolved_user_id and not resolved_company_id:
        existing_user = db.query(User).filter(User.id == resolved_user_id).first()
        if existing_user and getattr(existing_user, "company_id", None):
            resolved_company_id = str(existing_user.company_id)

    if resolved_company_id and not resolved_user_id:
        existing_user = (
            db.query(User)
            .filter(User.company_id == resolved_company_id)
            .order_by(User.created_at.asc())
            .first()
        )
        if existing_user:
            resolved_user_id = str(existing_user.id)

    if not resolved_company_id:
        preferred_user = (
            db.query(User)
            .filter(User.company_id.isnot(None))
            .order_by(User.created_at.asc())
            .first()
        )
        if preferred_user and getattr(preferred_user, "company_id", None):
            resolved_company_id = str(preferred_user.company_id)
            if not resolved_user_id:
                resolved_user_id = str(preferred_user.id)

    if not resolved_company_id:
        company = (
            db.query(Company)
            .filter(Company.is_active == True)
            .order_by(Company.created_at.asc())
            .first()
        )
        if not company:
            company = Company(
                name="Empresa Padrão",
                description="Empresa criada automaticamente para o SuperAgent",
                is_active=True,
            )
            db.add(company)
            db.commit()
            db.refresh(company)
        resolved_company_id = str(company.id)

    if not resolved_user_id:
        user = (
            db.query(User)
            .filter(User.company_id == resolved_company_id)
            .order_by(User.created_at.asc())
            .first()
        )
        if not user:
            user = db.query(User).order_by(User.created_at.asc()).first()
        if not user:
            user = User(
                email="admin@neuralilux.com",
                hashed_password="default",
                full_name="Administrador",
                company_id=resolved_company_id,
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        resolved_user_id = str(user.id)

    return resolved_company_id, resolved_user_id


__all__ = ["resolve_agent_chat_actor", "run_sync"]