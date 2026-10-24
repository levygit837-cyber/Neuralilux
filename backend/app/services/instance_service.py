"""Escritas na Instance (criação/assunção, resposta automática, vínculo do Agent e desativação). Cada função comita uma vez."""
from sqlalchemy.orm import Session

from app.core.database import commit_or_rollback
from app.models import Instance, User
from app.services.company_service import company_agent


def set_agent_enabled(db: Session, instance: Instance, enabled: bool) -> None:
    """Liga ou desliga a resposta automática da Instance."""
    instance.agent_enabled = enabled
    commit_or_rollback(db)
    db.refresh(instance)


def bind_agent(db: Session, instance: Instance, agent_id: str | None) -> bool:
    """Vincula o Agent (ou desvincula, com `None`). Ao desvincular com a resposta automática ligada, desliga-a.

    Devolve se a resposta automática foi desligada.
    """
    instance.agent_id = agent_id
    disabled = agent_id is None and bool(instance.agent_enabled)
    if disabled:
        instance.agent_enabled = False
    commit_or_rollback(db)
    db.refresh(instance)
    return disabled


def deactivate(db: Session, local_id: str) -> None:
    """Desativa a linha local; a linha fica, pois Conversations e Messages a referenciam."""
    instance = db.get(Instance, local_id)
    instance.is_active = False
    instance.agent_enabled = False
    instance.status = "disconnected"
    commit_or_rollback(db)


def upsert_instance_for_user(db: Session, name: str, user: User, instance: Instance | None) -> Instance:
    """Cria ou assume a Instance local do usuário e comita (uma operação, um commit).

    `instance` é a linha local de `name` (ativa ou não) que a rota acabou de autorizar com `check_create_access`, ou
    `None` para criar. Falha no commit (`IntegrityError` numa criação concorrente do mesmo nome, por exemplo) faz
    `rollback` e sobe. A Instance volta carregada (`refresh`).

    Só `POST /instances/{name}` chama isto, depois de a Evolution criar a Instance (ou, para o
    superusuário, de ela já existir lá).
    - Nova, ou sem dono (só superusuário chega aqui): dono e Company vêm do usuário.
    - Do próprio usuário sem Company: ganha a Company do usuário.
    - De outro dono (superusuário importando): dono e Company não mudam.
    - Liga o Agent ativo da Company (e `agent_enabled=True`) quando a Instance não tem Agent e acabou de
      ser criada, assumida ou ganhou Company. Fora disso o vínculo não é refeito, para não desfazer um
      desvínculo feito pelo usuário.
    """
    rebind = False

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
        rebind = True
    else:
        if instance.owner_id is None:
            instance.owner_id = user.id
            instance.company_id = instance.company_id or user.company_id
            rebind = True
        elif instance.owner_id == user.id and instance.company_id is None and user.company_id:
            instance.company_id = user.company_id
            rebind = True
        if not instance.is_active:
            instance.is_active = True
        if not instance.name:
            instance.name = name

    if rebind and not instance.agent_id:
        agent = company_agent(db, instance.company_id)
        if agent:
            instance.agent_id = agent.id
            instance.agent_enabled = True

    commit_or_rollback(db)
    db.refresh(instance)
    return instance
