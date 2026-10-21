"""
Instances: Agent da Instance (liga/desliga as respostas automáticas e vincula o Agent).

Cada rota faz upsert da Instance local para o usuário (`upsert_instance_for_user`): dono e Company
vêm do usuário, o Agent ativo da Company é ligado e Instance de outro dono responde 403.

- GET   /{instance_id}/agent-status
- PATCH /{instance_id}/agent-status
- PATCH /{instance_id}/agent-binding
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
import structlog

from app.api.access import upsert_instance_for_user
from app.api.deps import get_current_user, get_db
from app.models import User, Instance, Agent

logger = structlog.get_logger()

router = APIRouter()


def _is_agent_auto_reply_active(instance: Instance) -> bool:
    if not instance.agent_enabled or not instance.agent_id:
        return False

    if not instance.agent or not instance.agent.is_active:
        return False

    return True


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
        instance = upsert_instance_for_user(db, instance_id, current_user)
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
        instance = upsert_instance_for_user(db, instance_id, current_user)

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
        instance = upsert_instance_for_user(db, instance_id, current_user)

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
