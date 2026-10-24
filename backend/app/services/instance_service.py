"""Escritas na Instance (resposta automática, vínculo do Agent e desativação). Cada função comita uma vez."""
from sqlalchemy.orm import Session

from app.models import Instance


def set_agent_enabled(db: Session, instance: Instance, enabled: bool) -> None:
    """Liga ou desliga a resposta automática da Instance."""
    instance.agent_enabled = enabled
    db.commit()
    db.refresh(instance)


def bind_agent(db: Session, instance: Instance, agent_id: str | None) -> bool:
    """Vincula o Agent (ou desvincula, com `None`). Ao desvincular com a resposta automática ligada, desliga-a.

    Devolve se a resposta automática foi desligada.
    """
    instance.agent_id = agent_id
    disabled = agent_id is None and bool(instance.agent_enabled)
    if disabled:
        instance.agent_enabled = False
    db.commit()
    db.refresh(instance)
    return disabled


def deactivate(db: Session, local_id: str) -> None:
    """Desativa a linha local; a linha fica, pois Conversations e Messages a referenciam."""
    instance = db.get(Instance, local_id)
    instance.is_active = False
    instance.agent_enabled = False
    instance.status = "disconnected"
    db.commit()
