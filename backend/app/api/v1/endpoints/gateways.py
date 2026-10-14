"""CRUD de gateways de inferencia (OpenAI-compatible), seus modelos e a atribuicao por tipo de agente.

Todas as rotas exigem usuario autenticado. A chave de API e criptografada em repouso e nunca e devolvida.
"""
from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.v1.endpoints.auth import get_current_user
from app.core.crypto import SecretDecryptionError, encrypt_secret
from app.core.database import get_db
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
from app.services import gateway_registry
from app.services.inference_service import InferenceServiceError

logger = structlog.get_logger()

router = APIRouter()


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
    gateway_registry.invalidate()


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
    _: User = Depends(get_current_user),
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
    agent_type: AgentType, db: Session = Depends(get_db), _: User = Depends(get_current_user)
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
    _: User = Depends(get_current_user),
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
def delete_model(model_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    model = _get_model(db, model_id)
    db.query(GatewayAssignment).filter(GatewayAssignment.gateway_model_id == model.id).delete()
    db.delete(model)
    _commit(db, "Falha ao remover modelo")


@router.post("/models/{model_id}/test", response_model=ProbeResponse)
async def test_model(model_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Uma chamada minima ao gateway com a configuracao salva (URL, chave, modelo, effort)."""
    model = _get_model(db, model_id)
    try:
        service = gateway_registry.build_service(model)
    except SecretDecryptionError as exc:
        return ProbeResponse(ok=False, error=str(exc))
    db.close()  # libera a conexao durante a chamada de rede
    try:
        result = await service.probe()
    except InferenceServiceError as exc:
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
    body: GatewayCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)
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
    _: User = Depends(get_current_user),
):
    gateway = _get_gateway(db, gateway_id)
    changes = body.model_dump(exclude_unset=True)
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
def delete_gateway(gateway_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
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
    _: User = Depends(get_current_user),
):
    _get_gateway(db, gateway_id)
    model = GatewayModel(gateway_id=gateway_id, **body.model_dump())
    db.add(model)
    _commit(db, "Ja existe um modelo com esse nome neste gateway")
    db.refresh(model)
    return model


@router.get("/{gateway_id}/remote-models", response_model=RemoteModelsResponse)
async def list_remote_models(
    gateway_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Ids que o gateway anuncia em `GET /models`, para preencher o cadastro de modelos."""
    gateway = _get_gateway(db, gateway_id)
    try:
        from app.core.crypto import decrypt_secret
        from app.services.gateway_inference_service import GatewayInferenceService

        service = GatewayInferenceService(
            base_url=gateway.base_url,
            model="",
            api_key=decrypt_secret(gateway.api_key_encrypted) if gateway.api_key_encrypted else None,
            timeout=float(gateway.timeout_seconds),
            gateway_name=gateway.name,
        )
    except SecretDecryptionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    db.close()
    try:
        return RemoteModelsResponse(models=await service.list_models())
    except InferenceServiceError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
