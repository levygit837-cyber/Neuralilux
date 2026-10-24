"""Dependências compartilhadas das rotas: sessão do banco e usuário autenticado."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import database
from app.services.user_service import get_active_user_from_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_db():
    db = database.SessionLocal()  # lido na chamada: os testes trocam o SessionLocal
    try:
        yield db
    finally:
        db.close()


def _user_from_token(token: str, db: Session):
    """Usuário ativo do JWT (mesma regra do handshake do Socket.IO); 401 se inválido, vencido, inexistente ou inativo."""
    user = get_active_user_from_token(db, token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Get current user from JWT token"""
    return _user_from_token(token, db)


async def get_optional_user(
    token: str | None = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
):
    """Usuário do JWT, ou None se não houver Authorization. Token presente mas inválido é 401."""
    if token is None:
        return None
    return _user_from_token(token, db)


async def require_superuser(current_user=Depends(get_current_user)):
    """Usuário do JWT, só se for superusuário; 403 para os demais."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a superuser can do this")
    return current_user
