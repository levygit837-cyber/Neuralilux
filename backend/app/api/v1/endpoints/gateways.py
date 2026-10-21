"""CRUD de Gateways de inferencia (protocolo Anthropic Messages), seus modelos e a atribuicao por tipo de agente.

Leitura exige usuario autenticado. Criar, editar, apagar, atribuir e testar exigem superuser: Gateways sao
globais e `base_url` e um alvo de SSRF (ADR 0002). A chave de API e criptografada em repouso e nunca e devolvida.
"""
from typing import List
from urllib.parse import urlparse

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.v1.endpoints.auth import get_current_user
from app.core.crypto import encrypt_secret
from app.core.database import get_db
from app.llm import registry
from app.llm.errors import LLMError, LLMNotConfiguredError, LLMProviderError
from app.models.models import GatewayAssignment, GatewayModel, InferenceGateway, User
from app.schemas.gateway import (
    AgentType,
    AssignmentResponse,
    AssignmentUpdate,
    GatewayCreate,
    GatewayModelCreate,
    GatewayModelResponse,
    GatewayModelUpdate,
    GatewayResponse,
    GatewayUpdate,
    ProbeResponse,
    RemoteModelsResponse,
)

logger = structlog.get_logger()

# Probe e listagem de modelos seguram a requisicao do operador: tentativa unica e timeout curto.
_ADMIN_CALL_OPTIONS = {"timeout": 15.0, "max_attempts": 1}
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _origin(url: str) -> tuple[str, str | None, int | None]:
    """(scheme, host, porta) normalizados: so a origem decide para onde a chave salva e enviada."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    return scheme, parsed.hostname, parsed.port or _DEFAULT_PORTS.get(scheme)

router = APIRouter()


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas superusuarios podem alterar ou testar gateways")
    return current_user


def _gateway_response(gateway: InferenceGateway) -> GatewayResponse:
    return GatewayResponse(
        id=gateway.id,
        name=gateway.name,
        base_url=gateway.base_url,
        has_api_key=bool(gateway.api_key_encrypted),
        timeout_seconds=gateway.timeout_seconds,
        is_active=gateway.is_active,
        models=[GatewayModelResponse.model_validate(m) for m in gateway.models],
        created_at=gateway.created_at,
    )


def _assignment_response(assignment: GatewayAssignment) -> AssignmentResponse:
    model = assignment.gateway_model
    return AssignmentResponse(
        agent_type=assignment.agent_type,
        gateway_model_id=model.id,
        gateway_id=model.gateway_id,
        gateway_name=model.gateway.name,
        model_name=model.name,
        model_id=model.model_id,
    )


def _get_gateway(db: Session, gateway_id: str) -> InferenceGateway:
    gateway = db.get(InferenceGateway, gateway_id)
    if gateway is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gateway nao encontrado")
    return gateway


def _get_model(db: Session, model_id: str) -> GatewayModel:
    model = db.get(GatewayModel, model_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Modelo nao encontrado")
    return model


def _commit(db: Session, conflict_detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, conflict_detail)
    registry.invalidate()


# --- atribuicoes (rotas estaticas antes de /{gateway_id}) ------------------- #

@router.get("/assignments", response_model=List[AssignmentResponse])
def list_assignments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(GatewayAssignment)
        .options(joinedload(GatewayAssignment.gateway_model).joinedload(GatewayModel.gateway))
        .order_by(GatewayAssignment.agent_type)
        .all()
    )
    return [_assignment_response(row) for row in rows]


@router.put("/assignments/{agent_type}", response_model=AssignmentResponse)
def set_assignment(
    agent_type: AgentType,
    body: AssignmentUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    model = _get_model(db, body.gateway_model_id)
    if not (model.is_active and model.gateway.is_active):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Modelo ou gateway inativo")

    assignment = db.get(GatewayAssignment, agent_type)
    if assignment is None:
        assignment = GatewayAssignment(agent_type=agent_type, gateway_model_id=model.id)
        db.add(assignment)
    else:
        assignment.gateway_model_id = model.id
    _commit(db, "Falha ao salvar atribuicao")
    db.refresh(assignment)
    return _assignment_response(assignment)


@router.delete("/assignments/{agent_type}", status_code=status.HTTP_204_NO_CONTENT)
def clear_assignment(
    agent_type: AgentType, db: Session = Depends(get_db), _: User = Depends(require_superuser)
):
    assignment = db.get(GatewayAssignment, agent_type)
    if assignment is not None:
        db.delete(assignment)
        _commit(db, "Falha ao remover atribuicao")


# --- modelos ----------------------------------------------------------------- #

@router.patch("/models/{model_id}", response_model=GatewayModelResponse)
def update_model(
    model_id: str,
    body: GatewayModelUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    model = _get_model(db, model_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field in ("name", "model_id", "supports_tools", "is_active"):
            continue  # campos obrigatorios: null nao limpa
        setattr(model, field, value)
    _commit(db, "Ja existe um modelo com esse nome neste gateway")
    db.refresh(model)
    return model


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: str, db: Session = Depends(get_db), _: User = Depends(require_superuser)):
    model = _get_model(db, model_id)
    db.query(GatewayAssignment).filter(GatewayAssignment.gateway_model_id == model.id).delete()
    db.delete(model)
    _commit(db, "Falha ao remover modelo")


@router.post("/models/{model_id}/test", response_model=ProbeResponse)
async def test_model(model_id: str, db: Session = Depends(get_db), _: User = Depends(require_superuser)):
    """Uma chamada minima (`max_tokens: 8`) ao Gateway com a configuracao salva (URL, chave, modelo, effort)."""
    model = _get_model(db, model_id)
    model_name, effort = model.model_id, model.reasoning_effort
    try:
        client = registry.build_client(model.gateway, **_ADMIN_CALL_OPTIONS)
    except LLMNotConfiguredError as exc:
        return ProbeResponse(ok=False, error=str(exc))
    db.close()  # libera a conexao durante a chamada de rede
    try:
        result = await client.probe(model=model_name, effort=effort)
    except LLMError as exc:
        return ProbeResponse(ok=False, error=str(exc))
    return ProbeResponse(ok=True, **result)


# --- gateways ---------------------------------------------------------------- #

@router.get("/", response_model=List[GatewayResponse])
def list_gateways(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = (
        db.query(InferenceGateway)
        .options(joinedload(InferenceGateway.models))
        .order_by(InferenceGateway.created_at)
        .all()
    )
    return [_gateway_response(g) for g in rows]


@router.post("/", response_model=GatewayResponse, status_code=status.HTTP_201_CREATED)
def create_gateway(
    body: GatewayCreate, db: Session = Depends(get_db), _: User = Depends(require_superuser)
):
    gateway = InferenceGateway(
        name=body.name.strip(),
        base_url=body.base_url,
        api_key_encrypted=encrypt_secret(body.api_key) if body.api_key else None,
        timeout_seconds=body.timeout_seconds,
        is_active=body.is_active,
    )
    db.add(gateway)
    _commit(db, "Ja existe um gateway com esse nome")
    db.refresh(gateway)
    return _gateway_response(gateway)


@router.get("/{gateway_id}", response_model=GatewayResponse)
def get_gateway(gateway_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _gateway_response(_get_gateway(db, gateway_id))


@router.patch("/{gateway_id}", response_model=GatewayResponse)
def update_gateway(
    gateway_id: str,
    body: GatewayUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    gateway = _get_gateway(db, gateway_id)
    changes = body.model_dump(exclude_unset=True)
    new_url = changes.get("base_url")
    if new_url is not None and _origin(new_url) != _origin(gateway.base_url) and "api_key" not in changes:
        # A chave salva seguiria para outra origem: exige informar a chave de novo (ou "" para apagar).
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Alterar a origem (esquema, host ou porta) do base_url exige informar api_key novamente "
            "(use string vazia para remover a chave salva)",
        )
    if "api_key" in changes:
        key = changes.pop("api_key")
        gateway.api_key_encrypted = encrypt_secret(key) if key else None
    for field, value in changes.items():
        if value is None:
            continue
        setattr(gateway, field, value.strip() if field == "name" else value)
    _commit(db, "Ja existe um gateway com esse nome")
    db.refresh(gateway)
    return _gateway_response(gateway)


@router.delete("/{gateway_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gateway(gateway_id: str, db: Session = Depends(get_db), _: User = Depends(require_superuser)):
    gateway = _get_gateway(db, gateway_id)
    model_ids = [m.id for m in gateway.models]
    if model_ids:
        db.query(GatewayAssignment).filter(
            GatewayAssignment.gateway_model_id.in_(model_ids)
        ).delete(synchronize_session=False)
    db.delete(gateway)
    _commit(db, "Falha ao remover gateway")


@router.post(
    "/{gateway_id}/models", response_model=GatewayModelResponse, status_code=status.HTTP_201_CREATED
)
def create_model(
    gateway_id: str,
    body: GatewayModelCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superuser),
):
    _get_gateway(db, gateway_id)
    model = GatewayModel(gateway_id=gateway_id, **body.model_dump())
    db.add(model)
    _commit(db, "Ja existe um modelo com esse nome neste gateway")
    db.refresh(model)
    return model


@router.get("/{gateway_id}/remote-models", response_model=RemoteModelsResponse)
async def list_remote_models(
    gateway_id: str, db: Session = Depends(get_db), _: User = Depends(require_superuser)
):
    """Ids que o Gateway anuncia em `GET {base_url}/v1/models`; sem essa rota (404), os modelos cadastrados."""
    gateway = _get_gateway(db, gateway_id)
    registered = [m.model_id for m in gateway.models]
    try:
        client = registry.build_client(gateway, **_ADMIN_CALL_OPTIONS)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    db.close()
    try:
        return RemoteModelsResponse(models=await client.list_models())
    except LLMProviderError as exc:
        if exc.status_code == 404:
            return RemoteModelsResponse(models=registered)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    except LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
