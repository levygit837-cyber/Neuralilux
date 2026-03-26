"""
WhatsApp Endpoints - QR Code, Status, and Disconnect.
Integrates with Evolution API service.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import structlog

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.models import User, Instance
from app.services.evolution_api import evolution_api, EvolutionAPIError

logger = structlog.get_logger()

router = APIRouter()


@router.get("/qr")
async def get_qr_code(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get QR code for WhatsApp connection.

    - **instance_id**: ID of the WhatsApp instance to connect.
    - Returns the QR code (base64) for scanning with WhatsApp mobile app.
    """
    # Verify instance exists and belongs to the user
    instance = db.query(Instance).filter(
        Instance.id == instance_id,
        Instance.is_active == True,
    ).first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found",
        )

    # Check ownership (non-superusers can only access their own instances)
    if not current_user.is_superuser and instance.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )

    try:
        # Fetch QR code from Evolution API
        result = await evolution_api.get_instance_qrcode(instance.evolution_instance_id)

        qr_code = result.get("qrcode", {}).get("base64") or result.get("base64") or result.get("code")

        if not qr_code:
            # Instance might already be connected
            status_result = await evolution_api.get_instance_status(instance.evolution_instance_id)
            state = status_result.get("instance", {}).get("state", "unknown")
            return {
                "instance_id": instance_id,
                "qr_code": None,
                "status": state,
                "message": f"Instance is already {state}. No QR code available.",
            }

        # Update instance status to connecting
        instance.status = "connecting"
        db.commit()

        return {
            "instance_id": instance_id,
            "qr_code": qr_code,
            "status": "connecting",
            "message": "Scan the QR code with WhatsApp to connect",
        }

    except EvolutionAPIError as e:
        logger.error("Failed to get QR code", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail=f"Evolution API error: {e.message}",
        )


@router.get("/status")
async def get_connection_status(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get WhatsApp connection status.

    - **instance_id**: ID of the WhatsApp instance.
    - Returns the current connection state (open, close, connecting, etc.).
    """
    instance = db.query(Instance).filter(
        Instance.id == instance_id,
        Instance.is_active == True,
    ).first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found",
        )

    if not current_user.is_superuser and instance.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )

    try:
        result = await evolution_api.get_instance_status(instance.evolution_instance_id)

        evolution_state = result.get("instance", {}).get("state", "unknown")

        state_mapping = {
            "open": "connected",
            "close": "disconnected",
            "connecting": "connecting",
            "closed": "disconnected",
        }
        mapped_status = state_mapping.get(evolution_state, evolution_state)

        if instance.status != mapped_status:
            instance.status = mapped_status
            db.commit()

        return {
            "instance_id": instance_id,
            "instance_name": instance.name,
            "evolution_instance_id": instance.evolution_instance_id,
            "status": mapped_status,
            "evolution_state": evolution_state,
            "phone_number": instance.phone_number,
        }

    except EvolutionAPIError as e:
        logger.error("Failed to get instance status", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail=f"Evolution API error: {e.message}",
        )


@router.post("/disconnect")
async def disconnect_whatsapp(
    instance_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Disconnect WhatsApp instance.

    - **instance_id**: ID of the WhatsApp instance to disconnect.
    - Logs out the WhatsApp session and updates instance status.
    """
    instance = db.query(Instance).filter(
        Instance.id == instance_id,
        Instance.is_active == True,
    ).first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found",
        )

    if not current_user.is_superuser and instance.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )

    if instance.status == "disconnected":
        return {
            "instance_id": instance_id,
            "status": "disconnected",
            "message": "Instance is already disconnected",
        }

    try:
        await evolution_api.disconnect_instance(instance.evolution_instance_id)

        instance.status = "disconnected"
        instance.qr_code = None
        db.commit()

        logger.info("Instance disconnected", instance_id=instance_id)

        return {
            "instance_id": instance_id,
            "status": "disconnected",
            "message": "WhatsApp instance disconnected successfully",
        }

    except EvolutionAPIError as e:
        logger.error("Failed to disconnect instance", instance_id=instance_id, error=e.message)
        raise HTTPException(
            status_code=e.status_code if e.status_code != 500 else status.HTTP_502_BAD_GATEWAY,
            detail=f"Evolution API error: {e.message}",
        )