"""
Instances: leitura e estado da conexão na Evolution API. Todas as rotas exigem login e só
alcançam Instances do usuário (superusuário: todas), via `app.api.access`.

- GET  /                       - lista as Instances do usuário com o estado atual na Evolution
- GET  /{instance_id}/status   - estado da conexão
- POST /{instance_id}/connect  - conecta (QR code)
- DELETE /{instance_id}/logout - desconecta
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
import structlog

from app.api.access import get_instance_for_user, instance_ids_for_user
from app.api.deps import get_current_user, get_db
from app.models import Instance, User
from app.whatsapp.evolution_client import evolution_api, EvolutionAPIError

logger = structlog.get_logger()

router = APIRouter()


def evolution_name(instance: Instance) -> str:
    """Nome da Instance na Evolution (`POST /{name}` grava o mesmo valor em name e evolution_instance_id)."""
    return instance.evolution_instance_id or instance.name


def _evolution_instance_name(inst: dict) -> str:
    nested = inst.get("instance") or {}
    return inst.get("name") or inst.get("instanceName") or nested.get("instanceName") or ""


def _active_instances(db: Session, user: User) -> list[Instance]:
    """Instances ativas do usuário (bloqueante: roda em thread), na ordem de criação."""
    query = db.query(Instance).filter(Instance.is_active == True)  # noqa: E712
    user_instance_ids = instance_ids_for_user(db, user)
    if user_instance_ids is not None:
        query = query.filter(Instance.id.in_(user_instance_ids))
    return query.order_by(Instance.created_at, Instance.id).all()


@router.get("/")
async def list_instances(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista as Instances do usuário (superusuário: todas), com o estado atual na Evolution API.

    As linhas locais mandam; a Evolution só acrescenta estado e perfil. O `token` da Evolution
    nunca é devolvido.
    """
    try:
        local_instances = await run_in_threadpool(_active_instances, db, current_user)

        evolution_by_name: dict[str, dict] = {}
        if local_instances:
            for inst in await evolution_api.fetch_instances():
                if isinstance(inst, dict):
                    evolution_by_name[_evolution_instance_name(inst)] = inst

        instances_list = []
        for local in local_instances:
            name = evolution_name(local)
            inst = evolution_by_name.get(name, {})
            nested = inst.get("instance") or {}
            profile = inst.get("profile") or {}
            instances_list.append({
                "id": local.id,
                "instance_id": name,
                "name": name,
                "status": inst.get("status") or inst.get("connectionStatus") or nested.get("state") or local.status or "unknown",
                "owner": inst.get("owner") or inst.get("ownerJid", ""),
                "owner_id": local.owner_id,
                "company_id": local.company_id,
                "agent_id": local.agent_id,
                "agent_enabled": bool(local.agent_enabled),
                "profile_name": inst.get("profileName") or profile.get("name", ""),
                "profile_pic_url": inst.get("profilePicUrl") or profile.get("pictureUrl", ""),
                "server_url": inst.get("serverUrl", ""),
            })

        return {
            "instances": instances_list,
            "total": len(instances_list),
        }

    except EvolutionAPIError as e:
        logger.error("Failed to fetch instances from Evolution API", error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail="Evolution API error",
        )
    except Exception:
        logger.exception("Unexpected error fetching instances")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch instances",
        )


@router.get("/{instance_id}/status")
async def get_instance_status(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the connection status of a WhatsApp instance.

    - **instance_id**: The instance id, Evolution instance name or name.
    - Returns the current connection state (open, close, connecting, etc.).
    """
    instance = await run_in_threadpool(get_instance_for_user, db, instance_id, current_user)
    try:
        result = await evolution_api.get_instance_status(evolution_name(instance))

        evolution_state = (
            result.get("instance", {}).get("state")
            or result.get("state")
            or result.get("connectionStatus")
            or "unknown"
        )

        state_mapping = {
            "open": "connected",
            "close": "disconnected",
            "closed": "disconnected",
            "connecting": "connecting",
            "disconnected": "disconnected",
            "connected": "connected",
        }
        mapped_status = state_mapping.get(evolution_state, evolution_state)

        return {
            "instance_id": instance_id,
            "status": mapped_status,
            "evolution_state": evolution_state,
            "raw": result,
        }

    except EvolutionAPIError as e:
        logger.error("Failed to get instance status", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail="Evolution API error",
        )
    except Exception:
        logger.exception("Unexpected error getting instance status", instance_id=instance_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status for instance {instance_id}",
        )


@router.post("/{instance_id}/connect")
async def connect_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Connect a WhatsApp instance by fetching the QR code.

    - **instance_id**: The instance id, Evolution instance name or name.
    - Returns QR code (base64) for scanning with WhatsApp mobile app.
    """
    instance = await run_in_threadpool(get_instance_for_user, db, instance_id, current_user)
    name_in_evolution = evolution_name(instance)
    try:
        result = await evolution_api.get_instance_qrcode(name_in_evolution)

        qr_code = (
            result.get("qrcode", {}).get("base64")
            or result.get("base64")
            or result.get("code")
            or result.get("qrcode", {}).get("code")
        )

        if not qr_code:
            status_result = await evolution_api.get_instance_status(name_in_evolution)
            state = status_result.get("instance", {}).get("state") or status_result.get("state", "unknown")
            return {
                "instance_id": instance_id,
                "qr_code": None,
                "status": state,
                "message": f"Instance is already {state}. No QR code available.",
            }

        return {
            "instance_id": instance_id,
            "qr_code": qr_code,
            "status": "connecting",
            "message": "Scan the QR code with WhatsApp to connect",
        }

    except EvolutionAPIError as e:
        logger.error("Failed to connect instance", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail="Evolution API error",
        )
    except Exception:
        logger.exception("Unexpected error connecting instance", instance_id=instance_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect instance {instance_id}",
        )


@router.delete("/{instance_id}/logout")
async def logout_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Logout/disconnect a WhatsApp instance.

    - **instance_id**: The instance id, Evolution instance name or name.
    - Logs out the WhatsApp session.
    """
    instance = await run_in_threadpool(get_instance_for_user, db, instance_id, current_user)
    try:
        result = await evolution_api.disconnect_instance(evolution_name(instance))

        return {
            "instance_id": instance_id,
            "status": "disconnected",
            "message": "WhatsApp instance logged out successfully",
            "raw": result,
        }

    except EvolutionAPIError as e:
        logger.error("Failed to logout instance", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail="Evolution API error",
        )
    except Exception:
        logger.exception("Unexpected error logging out instance", instance_id=instance_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to logout instance {instance_id}",
        )
