"""
WhatsApp Instances Endpoints.

Provides endpoints for managing WhatsApp instances via Evolution API:
- GET  /                     - List all instances (fetchInstances) - NO AUTH REQUIRED
- GET  /{instance_id}/status - Get instance connection state - NO AUTH REQUIRED
- POST /{instance_id}/connect - Connect instance (get QR code)
- DELETE /{instance_id}/logout - Logout/disconnect instance
- DELETE /{instance_id}       - Delete instance
- POST /{instance_id}        - Create new instance (auth required)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
import structlog

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.models import User, Instance, Agent
from app.services.evolution_api import evolution_api, EvolutionAPIError

logger = structlog.get_logger()

router = APIRouter()


def _get_or_create_instance_for_agent_status(
    db: Session,
    instance_id: str,
    current_user: User,
) -> tuple[Instance, bool]:
    instance = db.query(Instance).filter(
        (Instance.evolution_instance_id == instance_id) | (Instance.name == instance_id)
    ).first()

    if instance:
        if current_user and instance.owner_id is None:
            instance.owner_id = current_user.id
        if not instance.name:
            instance.name = instance_id
        if not instance.evolution_instance_id:
            instance.evolution_instance_id = instance_id
        return instance, False

    instance = Instance(
        name=instance_id,
        evolution_instance_id=instance_id,
        status="disconnected",
        is_active=True,
        owner_id=current_user.id if current_user else None,
        agent_enabled=False,
    )
    db.add(instance)
    return instance, True


def _is_agent_auto_reply_active(instance: Instance) -> bool:
    if not instance.agent_enabled or not instance.agent_id:
        return False

    if not instance.agent or not instance.agent.is_active:
        return False

    return True


@router.get("/")
async def list_instances(db: Session = Depends(get_db)):
    """
    List all WhatsApp instances from Evolution API.

    This endpoint does NOT require authentication to allow
    the frontend to fetch instances freely.

    Returns a list of instances with their current status from Evolution API.
    """
    try:
        evolution_instances = await evolution_api.fetch_instances()

        instances_list = []
        for inst in evolution_instances:
            if isinstance(inst, dict):
                instance_data = {
                    "instance_id": inst.get("name") or inst.get("instanceName") or inst.get("instance", {}).get("instanceName", ""),
                    "name": inst.get("name") or inst.get("instanceName") or inst.get("instance", {}).get("instanceName", ""),
                    "status": inst.get("status") or inst.get("connectionStatus") or inst.get("instance", {}).get("state", "unknown"),
                    "owner": inst.get("owner") or inst.get("ownerJid", ""),
                    "profile_name": inst.get("profileName") or inst.get("profile", {}).get("name", ""),
                    "profile_pic_url": inst.get("profilePicUrl") or inst.get("profile", {}).get("pictureUrl", ""),
                    "token": inst.get("token", ""),
                    "server_url": inst.get("serverUrl", ""),
                }
                instances_list.append(instance_data)

        return {
            "instances": instances_list,
            "total": len(instances_list),
        }

    except EvolutionAPIError as e:
        logger.error("Failed to fetch instances from Evolution API", error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail=f"Evolution API error: {e.message}",
        )
    except Exception as e:
        logger.error("Unexpected error fetching instances", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch instances",
        )


@router.get("/{instance_id}/status")
async def get_instance_status(instance_id: str, db: Session = Depends(get_db)):
    """
    Get the connection status of a WhatsApp instance.

    This endpoint does NOT require authentication.

    - **instance_id**: The Evolution API instance name.
    - Returns the current connection state (open, close, connecting, etc.).
    """
    try:
        result = await evolution_api.get_instance_status(instance_id)

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
            detail=f"Evolution API error: {e.message}",
        )
    except Exception as e:
        logger.error("Unexpected error getting instance status", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status for instance {instance_id}",
        )


@router.post("/{instance_id}/connect")
async def connect_instance(instance_id: str, db: Session = Depends(get_db)):
    """
    Connect a WhatsApp instance by fetching the QR code.

    - **instance_id**: The Evolution API instance name.
    - Returns QR code (base64) for scanning with WhatsApp mobile app.
    """
    try:
        result = await evolution_api.get_instance_qrcode(instance_id)

        qr_code = (
            result.get("qrcode", {}).get("base64")
            or result.get("base64")
            or result.get("code")
            or result.get("qrcode", {}).get("code")
        )

        if not qr_code:
            status_result = await evolution_api.get_instance_status(instance_id)
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
            detail=f"Evolution API error: {e.message}",
        )
    except Exception as e:
        logger.error("Unexpected error connecting instance", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect instance {instance_id}",
        )


@router.delete("/{instance_id}/logout")
async def logout_instance(instance_id: str, db: Session = Depends(get_db)):
    """
    Logout/disconnect a WhatsApp instance.

    - **instance_id**: The Evolution API instance name.
    - Logs out the WhatsApp session.
    """
    try:
        result = await evolution_api.disconnect_instance(instance_id)

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
            detail=f"Evolution API error: {e.message}",
        )
    except Exception as e:
        logger.error("Unexpected error logging out instance", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to logout instance {instance_id}",
        )


@router.delete("/{instance_id}")
async def delete_instance_endpoint(instance_id: str, db: Session = Depends(get_db)):
    """
    Delete a WhatsApp instance from Evolution API.

    - **instance_id**: The Evolution API instance name.
    - Permanently deletes the instance.
    """
    try:
        result = await evolution_api.delete_instance(instance_id)

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
            detail=f"Evolution API error: {e.message}",
        )
    except Exception as e:
        logger.error("Unexpected error deleting instance", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete instance {instance_id}",
        )


class AgentStatusUpdate(BaseModel):
    agent_enabled: bool


class AgentBindingUpdate(BaseModel):
    agent_id: str | None = None


def _get_accessible_agent(
    db: Session,
    agent_id: str,
    current_user: User,
) -> Agent | None:
    query = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.is_active == True,
    )

    if not current_user.is_superuser:
        query = query.filter(
            or_(Agent.owner_id == current_user.id, Agent.owner_id.is_(None))
        )

    return query.first()


@router.get("/{instance_id}/agent-status")
async def get_agent_status(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get agent status for a WhatsApp instance.

    - **instance_id**: The instance name or ID.
    - Returns the current agent_enabled status.
    """
    try:
        instance, created = _get_or_create_instance_for_agent_status(db, instance_id, current_user)

        if created or db.is_modified(instance):
            db.commit()
            db.refresh(instance)

        return {
            "instance_id": instance.id,
            "instance_name": instance.name,
            "agent_enabled": _is_agent_auto_reply_active(instance),
            "agent_id": instance.agent_id,
            "agent_name": instance.agent.name if instance.agent else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting agent status", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent status for instance {instance_id}",
        )


@router.patch("/{instance_id}/agent-status")
async def update_agent_status(
    instance_id: str,
    status_update: AgentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Toggle agent enabled/disabled for a WhatsApp instance.

    - **instance_id**: The instance name or ID.
    - **agent_enabled**: Boolean to enable/disable agent responses.
    """
    try:
        instance, _ = _get_or_create_instance_for_agent_status(db, instance_id, current_user)

        if status_update.agent_enabled:
            if not instance.agent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Assign an agent to this instance before enabling automatic responses.",
                )

            agent = _get_accessible_agent(db, instance.agent_id, current_user)
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The assigned agent is unavailable or inactive.",
                )

        instance.agent_enabled = status_update.agent_enabled
        db.commit()
        db.refresh(instance)

        logger.info(
            "Agent status updated",
            instance_id=instance.id,
            instance_name=instance.name,
            agent_enabled=status_update.agent_enabled,
        )

        return {
            "instance_id": instance.id,
            "instance_name": instance.name,
            "agent_enabled": _is_agent_auto_reply_active(instance),
            "agent_id": instance.agent_id,
            "agent_name": instance.agent.name if instance.agent else None,
            "message": f"Agent {'enabled' if status_update.agent_enabled else 'disabled'} successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating agent status", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent status for instance {instance_id}",
        )


@router.patch("/{instance_id}/agent-binding")
async def update_agent_binding(
    instance_id: str,
    binding_update: AgentBindingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bind or unbind a WhatsApp agent from an instance.

    - **instance_id**: The instance name or ID.
    - **agent_id**: Agent ID to bind. Send null to unbind.
    """
    try:
        instance, _ = _get_or_create_instance_for_agent_status(db, instance_id, current_user)

        agent_name = None
        message = "Agent unbound successfully"

        if binding_update.agent_id:
            agent = _get_accessible_agent(db, binding_update.agent_id, current_user)
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Active agent {binding_update.agent_id} not found",
                )

            instance.agent_id = agent.id
            agent_name = agent.name
            message = "Agent bound successfully"
        else:
            instance.agent_id = None
            if instance.agent_enabled:
                instance.agent_enabled = False
                message = "Agent unbound successfully and automatic responses disabled"

        db.commit()
        db.refresh(instance)

        logger.info(
            "Agent binding updated",
            instance_id=instance.id,
            instance_name=instance.name,
            agent_id=instance.agent_id,
            agent_enabled=instance.agent_enabled,
        )

        return {
            "instance_id": instance.id,
            "instance_name": instance.name,
            "agent_enabled": _is_agent_auto_reply_active(instance),
            "agent_id": instance.agent_id,
            "agent_name": agent_name or (instance.agent.name if instance.agent else None),
            "message": message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating agent binding", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent binding for instance {instance_id}",
        )


@router.post("/{instance_id}")
async def create_or_connect_instance(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new WhatsApp instance in Evolution API and connect it.

    Requires authentication.

    - **instance_id**: Name for the new Evolution API instance.
    - Creates the instance and returns QR code for connection.
    """
    try:
        create_result = await evolution_api.create_instance(instance_id)

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
            "status": "created",
            "qr_code": qr_code,
            "message": "Instance created. Scan QR code to connect." if qr_code else "Instance created. Use /connect to get QR code.",
            "raw": create_result,
        }

    except EvolutionAPIError as e:
        logger.error("Failed to create instance", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail=f"Evolution API error: {e.message}",
        )
    except Exception as e:
        logger.error("Unexpected error creating instance", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create instance {instance_id}",
        )
