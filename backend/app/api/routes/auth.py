import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.api.deps import get_current_user, get_db, get_optional_user
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
        return create_user(db, user)
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


@router.post("/login", response_model=Token, dependencies=[Depends(limit_login)])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login and get access token. Rate limit por IP (429 com Retry-After; 503 se o Redis falha)."""
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

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user = Depends(get_current_user)):
    """Get current user information"""
    return current_user
