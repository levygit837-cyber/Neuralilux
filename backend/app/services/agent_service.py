"""Quais Agents um usuário acessa e qual Agent roda o Turn de uma Instance.

O limite é a Company: `Agent.company_id` igual à Company do usuário (ou da Instance, no Turn). O superusuário vê
todos. `Agent.owner_id` não entra em nenhuma decisão de acesso. Nenhuma função daqui escreve ou faz commit: criar o
Agent padrão da Company e ligá-lo à Instance é trabalho de caminhos explícitos (`upsert_instance_for_user`, seed).
"""
from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from app.models import Agent, Instance, User
from app.services.company_service import company_agent


def agents_for_user(db: Session, user: User) -> Query:
    """Agents ativos da Company do usuário; todos para o superusuário. Usuário sem Company não vê nenhum."""
    query = db.query(Agent).filter(Agent.is_active == True)  # noqa: E712
    if user.is_superuser:
        return query
    if user.company_id is None:
        return query.filter(false())
    return query.filter(Agent.company_id == user.company_id)


def get_agent_for_instance(db: Session, agent_id: str, user: User, instance: Instance) -> Agent | None:
    """O Agent ativo `agent_id` se o usuário pode usá-lo na Instance, senão `None` (a rota responde 404).

    Fora o superusuário, o Agent precisa ser da Company do usuário e da Company da Instance.
    """
    agent = agents_for_user(db, user).filter(Agent.id == agent_id).first()
    if agent is None or user.is_superuser:
        return agent
    return agent if agent.company_id == instance.company_id else None


def resolve_turn_agent(db: Session, instance: Instance) -> Agent | None:
    """O Agent que roda o Turn da Instance: o ligado a ela e, na falta, o Agent ativo da Company.

    O ligado só vale se ativo e da mesma Company da Instance. É a única resolução do Turn: o consumer chama aqui e o
    Agent segue até o executor, que não escolhe outro. Só lê; a Instance não é alterada nem há commit.
    """
    if instance.company_id is None:
        return None
    if instance.agent_id:
        bound = (
            db.query(Agent)
            .filter(
                Agent.id == instance.agent_id,
                Agent.company_id == instance.company_id,
                Agent.is_active == True,  # noqa: E712
            )
            .first()
        )
        if bound is not None:
            return bound
    return company_agent(db, instance.company_id)
