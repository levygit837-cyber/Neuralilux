"""
Instances: Agent da Instance (liga/desliga as respostas automáticas e vincula o Agent).

Nenhuma destas rotas cria Instance: resolvem a linha local pelo helper de acesso (`get_instance_for_user`),
com 404 se ela não existe e 403 se é de outro dono ou sem dono. Quem registra a Instance é
`POST /instances/{name}`. O GET não escreve nada.

- GET   /{instance_id}/agent-status
- PATCH /{instance_id}/agent-status
- PATCH /{instance_id}/agent-binding
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import structlog

from app.api.access import get_instance_for_user
from app.api.deps import get_current_user, get_db
from app.models import User, Instance
from app.services.agent_service import get_agent_for_instance, resolve_turn_agent

logger = structlog.get_logger()

router = APIRouter()


def _agent_state(db: Session, instance: Instance) -> dict:
    """O Agent da Instance como o Turn o enxerga (`resolve_turn_agent`), sem gravar nada.

    `agent_id` e `agent_name` são os do Agent que responderia: o vinculado e, na falta dele (Instance legada sem
    `agent_id`, vínculo inativo ou de outra Company), o ativo mais antigo da Company. A resposta automática só
    está ativa se há esse Agent e `agent_enabled` está ligado.
    """
    agent = resolve_turn_agent(db, instance)
    return {
        "instance_id": instance.id,
        "instance_name": instance.name,
        "agent_enabled": bool(instance.agent_enabled and agent),
        "agent_id": agent.id if agent else None,
        "agent_name": agent.name if agent else None,
    }


class AgentStatusUpdate(BaseModel):
    agent_enabled: bool


class AgentBindingUpdate(BaseModel):
    agent_id: str | None = None


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
        instance = get_instance_for_user(db, instance_id, current_user)

        return _agent_state(db, instance)

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
        instance = get_instance_for_user(db, instance_id, current_user)

        if status_update.agent_enabled and resolve_turn_agent(db, instance) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assign an agent to this instance before enabling automatic responses.",
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
            **_agent_state(db, instance),
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
        instance = get_instance_for_user(db, instance_id, current_user)

        message = "Agent unbound successfully"

        if binding_update.agent_id:
            agent = get_agent_for_instance(db, binding_update.agent_id, current_user, instance)
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Active agent {binding_update.agent_id} not found",
                )

            instance.agent_id = agent.id
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

        return {**_agent_state(db, instance), "message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating agent binding", instance_id=instance_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent binding for instance {instance_id}",
        )
