"""Dependências compartilhadas das rotas: sessão do banco e usuário autenticado."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core import database
from app.core.security import decode_access_token
from app.services.user_service import get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_db():
    db = database.SessionLocal()  # lido na chamada: os testes trocam o SessionLocal
    try:
        yield db
    finally:
        db.close()


def _user_from_token(token: str, db: Session):
    """Decodifica o JWT e devolve o usuário; 401 se o token for inválido ou o usuário não existir."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)  # None se o token é inválido ou expirou
    if payload is None:
        raise credentials_exception
    email: str | None = payload.get("sub")
    if email is None:
        raise credentials_exception

    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
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
