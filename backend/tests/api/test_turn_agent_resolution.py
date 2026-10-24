"""Qual Agent roda o Turn da Instance: o ligado a ela, da própria Company, sem escrever no banco."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.models import Agent, Instance
from app.services.agent_service import resolve_turn_agent
from tests.access_helpers import make_company


_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _agent(db, company, name, age_days=0, **extra) -> Agent:
    """`age_days` maior = mais novo. `created_at` explícito: o `now()` do SQLite tem resolução de segundo e empata."""
    agent = Agent(
        name=name,
        system_prompt="p",
        company_id=company.id,
        is_active=True,
        created_at=_EPOCH + timedelta(days=age_days),
        **extra,
    )
    db.add(agent)
    db.commit()
    return agent


def _instance(db, company, **extra) -> Instance:
    instance = Instance(name="loja", evolution_instance_id="evo-loja", company_id=company.id, **extra)
    db.add(instance)
    db.commit()
    return instance


def test_the_agent_bound_to_the_instance_wins_over_the_oldest_of_the_company(db):
    company = make_company(db, "Pizzaria")
    _agent(db, company, "Mais antigo")
    bound = _agent(db, company, "Vinculado", age_days=1, temperature=0.2, max_tokens=700)
    instance = _instance(db, company, agent_id=bound.id)

    assert resolve_turn_agent(db, instance).id == bound.id


def test_without_a_bound_agent_the_oldest_active_agent_of_the_company_is_used(db):
    company = make_company(db, "Pizzaria")
    oldest = _agent(db, company, "Mais antigo")
    _agent(db, company, "Mais novo", age_days=1)
    instance = _instance(db, company)

    assert resolve_turn_agent(db, instance).id == oldest.id


def test_a_bound_agent_from_another_company_is_ignored(db):
    mine = make_company(db, "Minha")
    other = make_company(db, "Alheia")
    own = _agent(db, mine, "Meu")
    foreign = _agent(db, other, "Alheio")
    instance = _instance(db, mine, agent_id=foreign.id)

    assert resolve_turn_agent(db, instance).id == own.id


def test_a_bound_agent_from_another_company_without_own_agent_resolves_to_none(db):
    mine = make_company(db, "Minha")
    foreign = _agent(db, make_company(db, "Alheia"), "Alheio")
    instance = _instance(db, mine, agent_id=foreign.id)

    assert resolve_turn_agent(db, instance) is None


def test_an_inactive_bound_agent_falls_back_to_the_active_one_of_the_company(db):
    company = make_company(db, "Pizzaria")
    inactive = _agent(db, company, "Inativo")
    inactive.is_active = False
    active = _agent(db, company, "Ativo", age_days=1)
    instance = _instance(db, company, agent_id=inactive.id)

    assert resolve_turn_agent(db, instance).id == active.id


def test_instance_without_company_has_no_agent(db):
    instance = Instance(name="solta", evolution_instance_id="evo-solta")
    db.add(instance)
    db.commit()

    assert resolve_turn_agent(db, instance) is None


def test_resolving_does_not_write_or_commit(db):
    company = make_company(db, "Pizzaria")
    oldest = _agent(db, company, "Mais antigo")
    instance = _instance(db, company)
    statements: list[str] = []
    commits: list[bool] = []
    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", lambda *args: statements.append(args[2]))
    event.listen(engine, "commit", lambda conn: commits.append(True))

    resolved = resolve_turn_agent(db, instance)

    assert resolved.id == oldest.id
    assert instance.agent_id is None  # a Instance continua sem vínculo: ligar é trabalho de caminho explícito
    assert not db.dirty and not db.new
    assert commits == []
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)
