"""Acesso por dono às Instances: um único lugar para resolver, autorizar e registrar Instances.

Regras:
- O dono (`Instance.owner_id`) e o superusuário acessam; qualquer outro recebe 403.
- Instance sem dono (legado) é só do superusuário.
- Só `POST /instances/{name}` cria ou assume a linha local, depois de a Evolution criar a Instance.
  Criar exige usuário com Company (ou superusuário): sem Company a Instance nasceria sem Agent nem escopo.
  As demais rotas só resolvem linhas que já existem (404 se não houver).
- Rotas que listam dados de Instances filtram por `instance_ids_for_user`.
"""
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Company, Instance, User
from app.services.company_service import company_agent


def resolve_instance(db: Session, instance_ref: str, *, only_active: bool = True) -> Instance | None:
    """Resolve a referência vinda do cliente (id, `evolution_instance_id` ou `name`, nessa precedência).

    Não é o lookup do worker: `app.whatsapp.status_events.find_instance` resolve só pelo nome da Evolution.
    """
    for column in (Instance.id, Instance.evolution_instance_id, Instance.name):
        query = db.query(Instance).filter(column == instance_ref)
        if only_active:
            query = query.filter(Instance.is_active == True)  # noqa: E712
        instance = query.order_by(Instance.created_at, Instance.id).first()
        if instance:
            return instance
    return None


def can_access_instance(instance: Instance, user: User) -> bool:
    """Dono ou superusuário. Instance sem dono só o superusuário."""
    return bool(user.is_superuser or (instance.owner_id is not None and instance.owner_id == user.id))


def get_instance_for_user(db: Session, instance_ref: str, user: User) -> Instance:
    """Instance ativa do usuário. 404 se não existe; 403 se é de outro dono ou sem dono (e o usuário não é superusuário)."""
    instance = resolve_instance(db, instance_ref)
    if not instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")
    if not can_access_instance(instance, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )
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


def get_company_for_user(db: Session, company_id: str, user: User) -> Company:
    """Company do próprio usuário (ou qualquer uma, para o superusuário).

    Quem não é da Company recebe 403 mesmo se o id não existe, para não revelar quais ids existem.
    """
    if not user.is_superuser and user.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions to access this company")
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def _find_by_evolution_name(db: Session, name: str) -> Instance | None:
    """A linha local do nome na Evolution, ativa ou não (é a chave única; `name` não é)."""
    return (
        db.query(Instance)
        .filter(Instance.evolution_instance_id == name)
        .order_by(Instance.created_at, Instance.id)
        .first()
    )


def check_create_access(db: Session, name: str, user: User) -> Instance | None:
    """Pode este usuário registrar `name`? Devolve a linha local existente (ou None) ou levanta 403.

    Chamar ANTES de falar com a Evolution. Linha de outro dono ou sem dono só é do superusuário. Quem não é
    superusuário precisa ter Company: sem ela, 403.
    """
    if not user.is_superuser and user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A Company is required to create an instance",
        )
    existing = _find_by_evolution_name(db, name)
    if existing is not None and not can_access_instance(existing, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )
    return existing


def upsert_instance_for_user(db: Session, name: str, user: User) -> Instance:
    """Cria ou assume a Instance local do usuário e comita (uma operação, um commit).

    `IntegrityError` (criação concorrente do mesmo nome) faz `rollback` e sobe. A Instance volta carregada (`refresh`).

    Só `POST /instances/{name}` chama isto, depois de a Evolution criar a Instance (ou, para o
    superusuário, de ela já existir lá).
    - Nova, ou sem dono (só superusuário chega aqui): dono e Company vêm do usuário.
    - Do próprio usuário sem Company: ganha a Company do usuário.
    - De outro dono (superusuário importando): dono e Company não mudam.
    - Liga o Agent ativo da Company (e `agent_enabled=True`) quando a Instance não tem Agent e acabou de
      ser criada, assumida ou ganhou Company. Fora disso o vínculo não é refeito, para não desfazer um
      desvínculo feito pelo usuário.
    """
    instance = check_create_access(db, name, user)
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

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(instance)
    return instance
