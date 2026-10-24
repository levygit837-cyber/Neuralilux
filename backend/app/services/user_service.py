from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, User
from app.schemas.user import UserCreate
from app.core.security import decode_access_token, get_password_hash, verify_password


class EmailAlreadyRegistered(Exception):
    """Já existe usuário com esse e-mail."""


class CompanyNotFound(Exception):
    """O `company_id` do cadastro não aponta para nenhuma Company."""


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email"""
    return db.query(User).filter(User.email == email).first()


def get_active_user_from_token(db: Session, token: str) -> Optional[User]:
    """Usuário ativo dono do JWT; `None` se o token é inválido ou vencido, o `sub` não existe ou o usuário está inativo.

    É a única regra de "token → usuário": a API HTTP (`app.api.deps`) e o handshake do Socket.IO a usam.
    """
    payload = decode_access_token(token)
    if payload is None:
        return None
    email = payload.get("sub")
    if not isinstance(email, str) or not email:
        return None
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    return user


def create_user(db: Session, user: UserCreate) -> User:
    """Cria o usuário com a senha em hash.

    `EmailAlreadyRegistered` se o e-mail já existe (inclusive quando a corrida é perdida no commit, pela
    constraint única) e `CompanyNotFound` se o `company_id` não existe.
    """
    if get_user_by_email(db, user.email) is not None:
        raise EmailAlreadyRegistered(user.email)
    if user.company_id is not None and db.get(Company, user.company_id) is None:
        raise CompanyNotFound(user.company_id)

    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        full_name=user.full_name,
        company_id=user.company_id,
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if get_user_by_email(db, user.email) is not None:
            raise EmailAlreadyRegistered(user.email) from exc
        raise
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password"""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
