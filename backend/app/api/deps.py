"""Dependências compartilhadas das rotas: sessão do banco e usuário autenticado."""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import database
from app.core.auth_cookie import AUTH_COOKIE_NAME
from app.services.user_service import get_active_user_from_token

# Sem auto_error: o token pode vir do cookie do navegador, e o 401 é decidido em `_token_of`.
bearer_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


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


def _token_of(request: Request, bearer: str | None) -> str | None:
    """JWT da requisição: `Authorization: Bearer` (scripts, e2e) vence o cookie `httpOnly` do navegador."""
    return bearer or request.cookies.get(AUTH_COOKIE_NAME)


async def get_current_user(
    request: Request,
    bearer: str | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Usuário do JWT (Bearer ou cookie); 401 sem token."""
    token = _token_of(request, bearer)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_token(token, db)


async def get_optional_user(
    request: Request,
    bearer: str | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Usuário do JWT, ou None se não houver Bearer nem cookie. Token presente mas inválido é 401."""
    token = _token_of(request, bearer)
    if token is None:
        return None
    return _user_from_token(token, db)


async def require_superuser(current_user=Depends(get_current_user)):
    """Usuário do JWT, só se for superusuário; 403 para os demais."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a superuser can do this")
    return current_user
