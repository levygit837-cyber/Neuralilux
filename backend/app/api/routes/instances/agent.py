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
from sqlalchemy import or_
from pydantic import BaseModel
import structlog

from app.api.access import get_instance_for_user
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
        instance = get_instance_for_user(db, instance_id, current_user)

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
        instance = get_instance_for_user(db, instance_id, current_user)

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
        instance = get_instance_for_user(db, instance_id, current_user)

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
# temp 0
# temp 1
# temp 2
# temp 3
# temp 4
# temp 5
# temp 6
# temp 7
# temp 8
# temp 9
# temp 10
# temp 11
# temp 12
# temp 13
# temp 14
# temp 15
# temp 16
# temp 17
# temp 18
# temp 19
# temp 20
# temp 21
# temp 22
# temp 23
# temp 24
# temp 25
# temp 26
# temp 27
# temp 28
# temp 29
# temp 30
# temp 31
# temp 32
# temp 33
# temp 34
# temp 35
# temp 36
# temp 37
# temp 38
# temp 39
# temp 40
# temp 41
# temp 42
# temp 43
# temp 44
# temp 45
# temp 46
# temp 47
# temp 48
# temp 49
# temp 50
# temp 51
# temp 52
# temp 53
# temp 54
# temp 55
# temp 56
# temp 57
# temp 58
# temp 59
# temp 60
# temp 61
# temp 62
# temp 63
# temp 64
# temp 65
# temp 66
# temp 67
# temp 68
# temp 69
# temp 70
# temp 71
# temp 72
# temp 73
# temp 74
# temp 75
# temp 76
# temp 77
# temp 78
# temp 79
# temp 80
# temp 81
# temp 82
# temp 83
# temp 84
# temp 85
# temp 86
# temp 87
# temp 88
# temp 89
# temp 90
# temp 91
# temp 92
# temp 93
# temp 94
# temp 95
# temp 96
# temp 97
# temp 98
# temp 99
# temp 100
# temp 101
# temp 102
# temp 103
# temp 104
# temp 105
# temp 106
# temp 107
# temp 108
# temp 109
# temp 110
# temp 111
# temp 112
# temp 113
# temp 114
# temp 115
# temp 116
# temp 117
# temp 118
# temp 119
# temp 120
# temp 121
# temp 122
# temp 123
# temp 124
# temp 125
# temp 126
# temp 127
# temp 128
# temp 129
# temp 130
# temp 131
# temp 132
# temp 133
# temp 134
# temp 135
# temp 136
# temp 137
# temp 138
# temp 139
# temp 140
# temp 141
# temp 142
# temp 143
# temp 144
# temp 145
# temp 146
# temp 147
# temp 148
# temp 149
# temp 150
# temp 151
# temp 152
# temp 153
# temp 154
# temp 155
# temp 156
# temp 157
# temp 158
# temp 159
# temp 160
# temp 161
# temp 162
# temp 163
# temp 164
# temp 165
# temp 166
# temp 167
# temp 168
# temp 169
# temp 170
# temp 171
# temp 172
# temp 173
# temp 174
# temp 175
# temp 176
# temp 177
# temp 178
# temp 179
# temp 180
# temp 181
# temp 182
# temp 183
# temp 184
# temp 185
# temp 186
# temp 187
# temp 188
# temp 189
# temp 190
# temp 191
# temp 192
# temp 193
# temp 194
# temp 195
# temp 196
# temp 197
# temp 198
# temp 199
