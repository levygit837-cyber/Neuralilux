import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, get_db, get_optional_user
from app.core.auth_cookie import clear_auth_cookie, set_auth_cookie
from app.core.config import settings
from app.core.rate_limit import limit_login, limit_register
from app.core.security import create_access_token
from app.schemas.user import UserCreate, UserResponse, Token
from app.services.user_service import CompanyNotFound, EmailAlreadyRegistered, authenticate_user, create_user

logger = structlog.get_logger()
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    user: UserCreate,
    db: Session = Depends(get_db),
    caller=Depends(get_optional_user),
):
    """Register a new user.

    Superusuário autenticado cria qualquer usuário, com ou sem Company, sem limite de tentativas. Os demais
    passam pelo rate limit por IP e só cadastram com `ALLOW_PUBLIC_REGISTRATION` ligada (padrão: desligada, 403);
    o registro público não escolhe Company: com `company_id`, só um superusuário cria o usuário.
    """
    is_superuser = bool(caller and caller.is_superuser)
    if not is_superuser:
        await limit_register(request)
        if not settings.ALLOW_PUBLIC_REGISTRATION:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Public registration is disabled")
    if user.company_id is not None and not is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a superuser can register a user into a Company",
        )
    try:
        return await run_in_threadpool(create_user, db, user)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except CompanyNotFound:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Company not found")
    except Exception:
        logger.exception("Unexpected error creating user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating user",
        )


@router.post("/login", response_model=Token, response_model_exclude_none=True, dependencies=[Depends(limit_login)])
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login: grava o JWT no cookie `httpOnly`. Navegador (requisição com `Origin`) só recebe o cookie, o JS nunca vê o
    token; clientes sem `Origin` (scripts, e2e com Bearer) recebem também `access_token` no corpo.

    Rate limit por IP (429 com Retry-After; 503 se o Redis falha)."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    set_auth_cookie(response, access_token)
    if request.headers.get("origin") is not None:
        return {"token_type": "bearer"}
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    """Encerra a sessão do navegador apagando o cookie. Sem autenticação: sair com cookie vencido tem de funcionar."""
    clear_auth_cookie(response)


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user = Depends(get_current_user)):
    """Get current user information"""
    return current_user
