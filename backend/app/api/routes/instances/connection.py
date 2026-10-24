"""
Instances: criação e remoção da Instance na Evolution API e na linha local. Todas as rotas exigem
login e só alcançam Instances do usuário (superusuário: todas), via `app.api.access`.

- DELETE /{instance_id} - apaga
- POST /{instance_id}   - cria na Evolution e registra a Instance local

As rotas de leitura e de estado da conexão ficam em `state.py`.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
import structlog

from app.api.access import check_create_access, get_instance_for_user, upsert_instance_for_user
from app.api.deps import get_current_user, get_db
from app.api.routes.instances.state import evolution_name
from app.models import Instance, User
from app.whatsapp.evolution_client import evolution_api, EvolutionAPIError

logger = structlog.get_logger()

router = APIRouter()


def _is_already_exists(error: EvolutionAPIError) -> bool:
    """A Evolution recusa criar um nome que já existe (hoje com 403 e \"already in use\"; aceita também 409)."""
    message = error.message.lower()
    return error.status_code in (403, 409) and ("already in use" in message or "already exists" in message)


async def _delete_orphan_in_evolution(instance_name: str) -> None:
    """Best-effort: remove da Evolution a Instance que esta requisição criou e cuja linha local não foi gravada.

    Falha só é logada: quem chama segue com o 409 e nunca o esconde.
    """
    try:
        await evolution_api.delete_instance(instance_name)
    except Exception as e:  # noqa: BLE001 - limpeza não pode mascarar o erro original
        logger.error(
            "Failed to delete orphan instance from Evolution API after local commit conflict",
            instance_id=instance_name,
            error=getattr(e, "message", str(e)),
        )


def _deactivate(db: Session, instance: Instance) -> None:
    """Desativa a linha local (bloqueante: roda em thread); a linha fica, pois Conversations e Messages a referenciam."""
    instance.is_active = False
    instance.agent_enabled = False
    instance.status = "disconnected"
    db.commit()


@router.delete("/{instance_id}")
async def delete_instance_endpoint(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a WhatsApp instance from Evolution API.

    - **instance_id**: The instance id, Evolution instance name or name.
    - Permanently deletes the instance in the Evolution and deactivates the local Instance
      (the row stays, since Conversations and Messages reference it). If the Evolution no longer
      has it (404), the local Instance is still deactivated.
    """
    instance = await run_in_threadpool(get_instance_for_user, db, instance_id, current_user)
    name_in_evolution = evolution_name(instance)
    try:
        try:
            result = await evolution_api.delete_instance(name_in_evolution)
        except EvolutionAPIError as e:
            if e.status_code != status.HTTP_404_NOT_FOUND:
                raise
            # Já não existe na Evolution: o que falta é só desativar a linha local.
            logger.info("Instance already gone from Evolution API", instance_id=instance_id)
            result = {"status": "NOT_FOUND"}

        await run_in_threadpool(_deactivate, db, instance)

        return {
            "instance_id": instance_id,
            "status": "deleted",
            "message": "WhatsApp instance deleted successfully",
            "raw": result,
        }

    except EvolutionAPIError as e:
        logger.error("Failed to delete instance", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail="Evolution API error",
        )
    except Exception:
        logger.exception("Unexpected error deleting instance", instance_id=instance_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete instance {instance_id}",
        )


def _save_instance(db: Session, instance_id: str, user: User) -> str:
    """Grava a linha local da Instance (bloqueante: roda em thread) e devolve o id. `IntegrityError` (criação
    concorrente do mesmo nome) sobe depois do rollback."""
    instance = upsert_instance_for_user(db, instance_id, user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    return instance.id


@router.post("/{instance_id}")
async def create_or_connect_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new WhatsApp instance in Evolution API, register it locally and connect it.

    Esta é a única rota que cria ou assume a linha local da Instance.

    - **instance_id**: Name for the new Evolution API instance.
    - 403 (antes de falar com a Evolution) se já existe uma linha local de outro dono ou sem dono e o
      usuário não é superusuário.
    - A linha local só é gravada DEPOIS de a Evolution criar a Instance, com o usuário como dono, a
      Company do usuário e o Agent ativo da Company (se houver).
    - Se a Evolution responde que o nome já existe: só o superusuário importa a Instance (upsert da
      linha local); qualquer outro recebe 409.
    - Criação concorrente do mesmo nome: 409. Se esta requisição criou a Instance na Evolution e o commit
      local falhou, ela tenta apagar a Instance órfã na Evolution (best-effort; falha só é logada).
    """
    is_superuser = current_user.is_superuser  # lido antes de qualquer commit: depois dele a leitura iria ao banco
    try:
        await run_in_threadpool(check_create_access, db, instance_id, current_user)

        created_here = True  # só esta requisição criou a Instance na Evolution (não foi "já existe")
        try:
            # O retorno traz o `hash` (token da Instance na Evolution): não vai para a resposta nem para o log.
            await evolution_api.create_instance(instance_id)
        except EvolutionAPIError as e:
            if not _is_already_exists(e):
                raise
            if not is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Instance {instance_id} already exists",
                )
            created_here = False

        try:
            local_id = await run_in_threadpool(_save_instance, db, instance_id, current_user)
        except IntegrityError:
            if created_here:
                await _delete_orphan_in_evolution(instance_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Instance {instance_id} was created concurrently",
            )

        qr_code = None
        try:
            connect_result = await evolution_api.get_instance_qrcode(instance_id)
            qr_code = (
                connect_result.get("qrcode", {}).get("base64")
                or connect_result.get("base64")
                or connect_result.get("code")
            )
        except EvolutionAPIError:
            pass

        return {
            "instance_id": instance_id,
            "id": local_id,
            "status": "created",
            "qr_code": qr_code,
            "message": "Instance created. Scan QR code to connect." if qr_code else "Instance created. Use /connect to get QR code.",
        }

    except HTTPException:
        await run_in_threadpool(db.rollback)
        raise
    except EvolutionAPIError as e:
        await run_in_threadpool(db.rollback)
        logger.error("Failed to create instance", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail="Evolution API error",
        )
    except Exception:
        await run_in_threadpool(db.rollback)
        logger.exception("Unexpected error creating instance", instance_id=instance_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create instance {instance_id}",
        )
