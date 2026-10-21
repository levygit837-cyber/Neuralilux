"""Acesso por dono às Instances: um único lugar para resolver, autorizar e criar Instances.

Regra: o dono (`Instance.owner_id`) e o superusuário acessam; qualquer outro recebe 403.
Rotas que listam dados de Instances filtram por `instance_ids_for_user`.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Agent, Instance, User


def find_instance(db: Session, instance_ref: str, *, only_active: bool = True) -> Instance | None:
    """Resolve uma Instance por id, `evolution_instance_id` ou `name`, nessa ordem de precedência."""
    for column in (Instance.id, Instance.evolution_instance_id, Instance.name):
        query = db.query(Instance).filter(column == instance_ref)
        if only_active:
            query = query.filter(Instance.is_active == True)  # noqa: E712
        instance = query.order_by(Instance.created_at, Instance.id).first()
        if instance:
            return instance
    return None


def _assert_can_access(instance: Instance, user: User) -> None:
    if not user.is_superuser and instance.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )


def get_instance_for_user(db: Session, instance_ref: str, user: User) -> Instance:
    """Instance ativa do usuário. 404 se não existe; 403 se é de outro dono (e o usuário não é superusuário)."""
    instance = find_instance(db, instance_ref)
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")
    _assert_can_access(instance, user)
    return instance


def instance_ids_for_user(db: Session, user: User) -> list[str] | None:
    """Ids das Instances ativas do usuário; `None` para o superusuário (todas, sem filtro)."""
    if user.is_superuser:
        return None
    rows = db.query(Instance.id).filter(
        Instance.owner_id == user.id,
        Instance.is_active == True,  # noqa: E712
    ).all()
    return [row.id for row in rows]


def company_agent(db: Session, company_id: str | None) -> Agent | None:
    """O Agent ativo da Company (o mesmo critério do worker em `_resolve_default_agent`)."""
    if not company_id:
        return None
    return (
        db.query(Agent)
        .filter(Agent.company_id == company_id, Agent.is_active == True)  # noqa: E712
        .order_by(Agent.created_at, Agent.id)
        .first()
    )


def upsert_instance_for_user(db: Session, name: str, user: User) -> Instance:
    """Cria ou atualiza a Instance local do usuário. Não faz commit: quem chama decide.

    - Existente de outro dono: 403 (sem tomada silenciosa). Sem dono (legado): o usuário assume.
    - Grava `owner_id`, `company_id` (do usuário) e `evolution_instance_id`.
    - Liga o Agent ativo da Company (e `agent_enabled=True`) quando a Instance não tem Agent e acabou de
      ser criada, assumida ou ganhou Company. Fora disso o vínculo não é refeito, para não desfazer um
      desvínculo feito pelo usuário.
    """
    instance = find_instance(db, name, only_active=False)

    if instance is None:
        instance = Instance(
            name=name,
            evolution_instance_id=name,
            status="disconnected",
            is_active=True,
            owner_id=user.id,
            company_id=user.company_id,
            agent_enabled=False,
        )
        db.add(instance)
        fresh = True
    else:
        fresh = False
        if instance.owner_id is None:
            instance.owner_id = user.id
            fresh = True
        _assert_can_access(instance, user)
        if instance.owner_id == user.id and instance.company_id is None and user.company_id:
            instance.company_id = user.company_id
            fresh = True
        if not instance.is_active:
            instance.is_active = True
        if not instance.name:
            instance.name = name
        if not instance.evolution_instance_id:
            instance.evolution_instance_id = name

    if fresh and not instance.agent_id:
        agent = company_agent(db, instance.company_id)
        if agent:
            instance.agent_id = agent.id
            instance.agent_enabled = True

    return instance
