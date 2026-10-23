"""scripts/seed_data.py: um Agent por Company, ligado às Instances da Company, de forma idempotente."""
import importlib.util
from pathlib import Path

import pytest

from app.models import Agent, BusinessType, Company, Instance, User

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "seed_data.py"


@pytest.fixture(scope="module")
def seed():
    spec = importlib.util.spec_from_file_location("seed_data_script", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _company(db, name: str) -> Company:
    business_type = db.query(BusinessType).first() or BusinessType(name="Restaurante", slug="restaurant")
    db.add(business_type)
    db.flush()
    company = Company(name=name, business_type_id=business_type.id)
    db.add(company)
    db.flush()
    return company


def _instance(db, evolution_id: str, company: Company | None) -> Instance:
    instance = Instance(
        name=evolution_id,
        evolution_instance_id=evolution_id,
        company_id=company.id if company else None,
        agent_enabled=False,  # como `instances.py` cria: o Agent só liga depois de atribuído
    )
    db.add(instance)
    db.flush()
    return instance


def test_each_company_gets_one_agent_and_its_instances_are_bound_to_it(db, seed):
    first, second = _company(db, "Empresa A"), _company(db, "Empresa B")
    a1, a2 = _instance(db, "evo-a1", first), _instance(db, "evo-a2", first)
    b1 = _instance(db, "evo-b1", second)

    seed.create_company_agents(db)

    agent_a = db.query(Agent).filter(Agent.company_id == first.id).one()
    agent_b = db.query(Agent).filter(Agent.company_id == second.id).one()
    assert agent_a.id != agent_b.id
    assert agent_a.is_active is True
    assert (a1.agent_id, a2.agent_id, b1.agent_id) == (agent_a.id, agent_a.id, agent_b.id)
    assert (a1.agent_enabled, a2.agent_enabled, b1.agent_enabled) == (True, True, True)  # seed novo já responde


def test_running_twice_does_not_duplicate_agents(db, seed):
    company = _company(db, "Empresa C")
    _instance(db, "evo-c1", company)

    seed.create_company_agents(db)
    created_again = seed.create_company_agents(db)

    assert db.query(Agent).filter(Agent.company_id == company.id).count() == 1
    assert created_again == []


def test_instance_without_company_stays_unbound(db, seed):
    orphan = _instance(db, "evo-orphan", None)

    seed.create_company_agents(db)

    assert orphan.agent_id is None
    assert not orphan.agent_enabled


def test_existing_binding_to_another_agent_is_kept(db, seed):
    company = _company(db, "Empresa D")
    custom = Agent(name="Custom", system_prompt="", company_id=company.id)
    db.add(custom)
    db.flush()
    bound = _instance(db, "evo-d1", company)
    bound.agent_id = custom.id

    seed.create_company_agents(db)

    assert bound.agent_id == custom.id
    assert db.query(Agent).filter(Agent.company_id == company.id).count() == 1


def test_rerunning_the_seed_does_not_reenable_an_instance_the_operator_disabled(db, seed):
    company = _company(db, "Empresa F")
    instance = _instance(db, "evo-f1", company)
    seed.create_company_agents(db)
    instance.agent_enabled = False
    db.commit()

    seed.create_company_agents(db)

    assert instance.agent_enabled is False


def test_agent_is_owned_by_a_user_of_the_company_when_there_is_one(db, seed):
    company = _company(db, "Empresa E")
    user = User(email="dono-e@example.com", hashed_password="x", company_id=company.id)
    db.add(user)
    db.flush()

    seed.create_company_agents(db)

    assert db.query(Agent).filter(Agent.company_id == company.id).one().owner_id == user.id


def test_seeded_agent_has_no_company_instructions(db, seed):
    company = _company(db, "Empresa G")
    _instance(db, "evo-g1", company)

    seed.create_company_agents(db)

    assert db.query(Agent).filter(Agent.company_id == company.id).one().system_prompt is None
