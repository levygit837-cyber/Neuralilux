"""Configuração da Company no painel: edição restrita ao dono, campos validados e Agent da Company."""

import pytest

from app.models import Agent, BusinessType, Company
from tests.access_helpers import make_company, make_user

HOURS = {
    "mon": [["11:00", "14:00"], ["18:00", "02:00"]],  # o segundo intervalo cruza a meia-noite
    "tue": [],
    "sun": [["18:00", "23:00"]],
}


@pytest.fixture
def world(client, db):
    mine = make_company(db, "Macedos", with_agent=True)
    other = make_company(db, "Outra", with_agent=True)
    return {
        "mine": mine,
        "other": other,
        "owner": make_user(client, db, "dono@example.com", company=mine),
        "stranger": make_user(client, db, "outro@example.com", company=other),
        "loner": make_user(client, db, "sem@example.com"),
        "admin": make_user(client, db, "admin@example.com", superuser=True),
    }


def put(client, company, headers, **fields):
    return client.put(f"/api/v1/companies/{company.id}", json=fields, headers=headers)


def stored(db, company) -> Company:
    db.expire_all()
    return db.get(Company, company.id)


# ---------- salvar e recarregar ----------


def test_owner_saves_every_company_field_and_reloads_them(client, db, world):
    response = put(
        client,
        world["mine"],
        world["owner"],
        address_street="Rua das Flores",
        address_number="100",
        address_neighborhood="Centro",
        address_city="Fortaleza",
        address_state="CE",
        phone="(85) 99999-0000",
        pix_key="pix@macedos.example",
        business_hours=HOURS,
        minimum_order="30.50",
        session_timeout_minutes=90,
        handoff_timeout_hours=6,
        timezone="America/Fortaleza",
    )
    assert response.status_code == 200, response.text

    reloaded = client.get(f"/api/v1/companies/{world['mine'].id}", headers=world["owner"]).json()
    assert reloaded["address_street"] == "Rua das Flores"
    assert reloaded["phone"] == "(85) 99999-0000"
    assert reloaded["pix_key"] == "pix@macedos.example"
    assert reloaded["business_hours"]["mon"] == [["11:00", "14:00"], ["18:00", "02:00"]]
    assert reloaded["minimum_order"] == 30.5
    assert reloaded["session_timeout_minutes"] == 90
    assert reloaded["handoff_timeout_hours"] == 6
    assert reloaded["timezone"] == "America/Fortaleza"
    assert stored(db, world["mine"]).pix_key == "pix@macedos.example"


def test_a_partial_update_keeps_the_other_fields(client, db, world):
    put(client, world["mine"], world["owner"], phone="(85) 1111-1111", pix_key="pix@macedos.example")
    put(client, world["mine"], world["owner"], phone="(85) 2222-2222")
    company = stored(db, world["mine"])
    assert (company.phone, company.pix_key) == ("(85) 2222-2222", "pix@macedos.example")


def test_blank_text_clears_the_field(client, db, world):
    put(client, world["mine"], world["owner"], pix_key="pix@macedos.example", phone="(85) 1111-1111")
    response = put(client, world["mine"], world["owner"], pix_key="  ", phone="")
    assert response.status_code == 200
    company = stored(db, world["mine"])
    assert company.pix_key is None and company.phone is None


def test_minimum_order_and_hours_can_be_cleared(client, db, world):
    put(client, world["mine"], world["owner"], minimum_order="20", business_hours=HOURS)
    assert put(client, world["mine"], world["owner"], minimum_order=None, business_hours=None).status_code == 200
    company = stored(db, world["mine"])
    assert company.minimum_order is None and company.business_hours is None


# ---------- quem pode editar ----------


@pytest.mark.parametrize("who", ["stranger", "loner"])
def test_another_company_gets_403_and_nothing_changes(client, db, world, who):
    response = put(client, world["mine"], world[who], pix_key="golpe@example.com")
    assert response.status_code == 403
    assert stored(db, world["mine"]).pix_key is None


@pytest.mark.parametrize("who", ["stranger", "loner"])
def test_another_company_cannot_read(client, world, who):
    assert client.get(f"/api/v1/companies/{world['mine'].id}", headers=world[who]).status_code == 403


# ---------- criar e desativar: só superusuário ----------


@pytest.fixture
def create_body(db):
    business_type = BusinessType(name="Restaurante", slug="restaurante")
    db.add(business_type)
    db.commit()
    return {"name": "Nova Pizzaria", "business_type_id": business_type.id}


@pytest.mark.parametrize("who", ["owner", "stranger", "loner"])
def test_a_regular_user_cannot_create_a_company(client, db, world, create_body, who):
    response = client.post("/api/v1/companies/", json=create_body, headers=world[who])
    assert response.status_code == 403
    assert db.query(Company).filter(Company.name == "Nova Pizzaria").count() == 0


def test_anonymous_cannot_create_a_company(client, db, create_body):
    assert client.post("/api/v1/companies/", json=create_body).status_code == 401
    assert db.query(Company).filter(Company.name == "Nova Pizzaria").count() == 0


def test_superuser_creates_a_company(client, db, world, create_body):
    response = client.post(
        "/api/v1/companies/", json={**create_body, "pix_key": "pix@nova.example"}, headers=world["admin"]
    )
    assert response.status_code == 201, response.text
    created = db.get(Company, response.json()["id"])
    assert (created.name, created.pix_key) == ("Nova Pizzaria", "pix@nova.example")


@pytest.mark.parametrize("who", ["owner", "stranger", "loner"])
def test_only_a_superuser_deactivates_a_company(client, db, world, who):
    """Nem o dono desativa a própria Company: `is_active` é do superusuário."""
    response = client.delete(f"/api/v1/companies/{world['mine'].id}", headers=world[who])
    assert response.status_code == 403
    assert stored(db, world["mine"]).is_active is True


def test_superuser_deactivates_a_company(client, db, world):
    response = client.delete(f"/api/v1/companies/{world['mine'].id}", headers=world["admin"])
    assert response.status_code == 204
    assert stored(db, world["mine"]).is_active is False


def test_deleting_a_missing_company_is_404_for_the_superuser(client, world):
    assert client.delete("/api/v1/companies/nao-existe", headers=world["admin"]).status_code == 404


@pytest.mark.parametrize("fields", [{"is_active": False}, {"business_type_id": "outro-ramo"}])
def test_owner_cannot_change_superuser_only_fields(client, db, world, fields):
    assert put(client, world["mine"], world["owner"], **fields).status_code == 403
    assert stored(db, world["mine"]).is_active is True


def test_anonymous_gets_401(client, world):
    response = client.put(f"/api/v1/companies/{world['mine'].id}", json={"phone": "(85) 99999-0000"})
    assert response.status_code == 401


def test_superuser_edits_any_company(client, db, world):
    assert put(client, world["other"], world["admin"], phone="(11) 3333-3333").status_code == 200
    assert stored(db, world["other"]).phone == "(11) 3333-3333"


def test_missing_company_is_404_for_the_superuser(client, world):
    response = client.put("/api/v1/companies/nao-existe", json={"phone": "(85) 99999-0000"}, headers=world["admin"])
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("who", "expected"),
    [("owner", ["mine"]), ("stranger", ["other"]), ("loner", []), ("admin", ["mine", "other"])],
)
def test_list_shows_only_the_own_company_unless_superuser(client, world, who, expected):
    listed = client.get("/api/v1/companies/", headers=world[who]).json()
    assert sorted(c["id"] for c in listed) == sorted(world[name].id for name in expected)


# ---------- validação ----------


@pytest.mark.parametrize(
    "fields",
    [
        {"business_hours": {"mon": [["25:00", "26:00"]]}},
        {"business_hours": {"mon": [["9:00", "18:00"]]}},
        {"business_hours": {"mon": [["10:00", "10:00"]]}},
        {"business_hours": {"mon": [["10:00", "14:00"], ["13:00", "18:00"]]}},
        {"business_hours": {"mon": [["18:00", "02:00"], ["23:00", "23:30"]]}},
        {"business_hours": {"monday": [["10:00", "18:00"]]}},
        {"business_hours": {"mon": [["10:00"]]}},
        {"business_hours": {"mon": "10:00-18:00"}},
        {"minimum_order": "-1"},
        {"minimum_order": "10.999"},
        {"minimum_order": "abc"},
        {"pix_key": "isto não é uma chave"},
        {"pix_key": "a" * 80 + "@x.com"},
        {"phone": "1" * 21},
        {"address_state": "CEA"},
        {"session_timeout_minutes": 0},
        {"session_timeout_minutes": 10081},
        {"session_timeout_minutes": None},
        {"handoff_timeout_hours": 0},
        {"handoff_timeout_hours": 721},
        {"handoff_timeout_hours": None},
        {"timezone": "Marte/Olympus"},
        {"name": ""},
        {"name": None},
        {"email": "nao-e-email"},
        {"phone": "abc"},
        {"phone": "(85) 9999x-0000"},
        {"phone": "123456"},
        {"phone": "----------"},
        {"handoff_timeout_hours": True},
        {"session_timeout_minutes": True},
        {"minimum_order": True},
        {"minimum_order": "NaN"},
        {"minimum_order": "Infinity"},
        {"minimum_order": "-Infinity"},
        {"minimum_order": "100000.01"},
        {"minimum_order": "99999999.99"},
    ],
)
def test_invalid_values_are_422_and_nothing_is_saved(client, db, world, fields):
    before = stored(db, world["mine"]).__dict__.copy()
    response = put(client, world["mine"], world["owner"], **{"phone": "(85) 99999-0000", **fields})
    assert response.status_code == 422, response.text
    company = stored(db, world["mine"])
    assert company.phone is None  # o campo válido do mesmo corpo também não entrou
    assert company.session_timeout_minutes == before["session_timeout_minutes"]


@pytest.mark.parametrize(
    "key",
    [
        "pix@macedos.example",
        "123e4567-e89b-12d3-a456-426614174000",
        "+5585999990000",
        "12345678909",
        "12345678000195",
    ],
)
def test_every_pix_key_kind_is_accepted(client, db, world, key):
    assert put(client, world["mine"], world["owner"], pix_key=key).status_code == 200
    assert stored(db, world["mine"]).pix_key == key


def test_overnight_interval_is_accepted_and_kept_as_typed(client, db, world):
    hours = {"fri": [["18:00", "00:00"]], "sat": [["22:00", "03:00"]]}
    assert put(client, world["mine"], world["owner"], business_hours=hours).status_code == 200
    assert stored(db, world["mine"]).business_hours == hours


@pytest.mark.parametrize("phone", ["(85) 99999-0000", "+55 85 99999-0000", "85999990000", "3333-3333"])
def test_common_phone_formats_are_accepted(client, db, world, phone):
    assert put(client, world["mine"], world["owner"], phone=phone).status_code == 200
    assert stored(db, world["mine"]).phone == phone


@pytest.mark.parametrize("value", ["0", "30.5", "100000"])
def test_minimum_order_accepts_zero_up_to_the_ceiling(client, db, world, value):
    assert put(client, world["mine"], world["owner"], minimum_order=value).status_code == 200
    assert float(stored(db, world["mine"]).minimum_order) == float(value)


# ---------- Agent da Company ----------


def agent_url(company):
    return f"/api/v1/companies/{company.id}/agent"


def test_owner_saves_and_reloads_agent_settings(client, db, world):
    saved = client.put(agent_url(world["mine"]), json={"temperature": 0.3, "max_tokens": 800}, headers=world["owner"])
    assert saved.status_code == 200, saved.text
    reloaded = client.get(agent_url(world["mine"]), headers=world["owner"]).json()
    assert (reloaded["temperature"], reloaded["max_tokens"]) == (0.3, 800)
    db.expire_all()
    agent = db.query(Agent).filter(Agent.company_id == world["mine"].id).one()
    assert (agent.temperature, agent.max_tokens) == (0.3, 800)


def test_agent_temperature_can_go_back_to_the_gateway_default(client, world):
    client.put(agent_url(world["mine"]), json={"temperature": 0.3}, headers=world["owner"])
    client.put(agent_url(world["mine"]), json={"temperature": None}, headers=world["owner"])
    assert client.get(agent_url(world["mine"]), headers=world["owner"]).json()["temperature"] is None


@pytest.mark.parametrize("fields", [{"temperature": 1.5}, {"temperature": -0.1}, {"max_tokens": 50}, {"max_tokens": 5000}, {"max_tokens": None}])
def test_invalid_agent_settings_are_422(client, world, fields):
    assert client.put(agent_url(world["mine"]), json=fields, headers=world["owner"]).status_code == 422


@pytest.mark.parametrize("who", ["stranger", "loner"])
def test_agent_of_another_company_is_403(client, db, world, who):
    assert client.get(agent_url(world["mine"]), headers=world[who]).status_code == 403
    response = client.put(agent_url(world["mine"]), json={"max_tokens": 300}, headers=world[who])
    assert response.status_code == 403
    db.expire_all()
    assert db.query(Agent).filter(Agent.company_id == world["mine"].id).one().max_tokens != 300


def test_company_without_agent_is_404(client, db, world):
    bare = make_company(db, "Sem Agent")
    assert client.get(agent_url(bare), headers=world["admin"]).status_code == 404


# ---------- Instruções da Company (Agent.system_prompt) ----------


def _instructions(client, world, who="owner"):
    return client.get(agent_url(world["mine"]), headers=world[who]).json()["system_prompt"]


def test_owner_saves_and_reloads_company_instructions(client, db, world):
    saved = client.put(agent_url(world["mine"]), json={"system_prompt": "  Seu nome é Ana.  "}, headers=world["owner"])
    assert saved.status_code == 200, saved.text
    assert saved.json()["system_prompt"] == "Seu nome é Ana."
    assert _instructions(client, world) == "Seu nome é Ana."
    db.expire_all()
    assert db.query(Agent).filter(Agent.company_id == world["mine"].id).one().system_prompt == "Seu nome é Ana."


def test_superuser_can_read_and_write_company_instructions(client, world):
    client.put(agent_url(world["mine"]), json={"system_prompt": "Tom formal."}, headers=world["admin"])
    assert _instructions(client, world, "admin") == "Tom formal."


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_blank_company_instructions_clear_the_field(client, world, blank):
    client.put(agent_url(world["mine"]), json={"system_prompt": "Seu nome é Ana."}, headers=world["owner"])
    assert client.put(agent_url(world["mine"]), json={"system_prompt": blank}, headers=world["owner"]).status_code == 200
    assert _instructions(client, world) is None


def test_company_instructions_are_kept_when_the_put_omits_them(client, world):
    client.put(agent_url(world["mine"]), json={"system_prompt": "Seu nome é Ana."}, headers=world["owner"])
    client.put(agent_url(world["mine"]), json={"max_tokens": 600}, headers=world["owner"])
    assert _instructions(client, world) == "Seu nome é Ana."


def test_company_instructions_above_the_limit_are_422_and_at_the_limit_are_saved(client, world):
    from app.schemas.company import AGENT_INSTRUCTIONS_MAX_LENGTH

    before = _instructions(client, world)
    over = client.put(
        agent_url(world["mine"]), json={"system_prompt": "a" * (AGENT_INSTRUCTIONS_MAX_LENGTH + 1)}, headers=world["owner"]
    )
    assert over.status_code == 422
    assert _instructions(client, world) == before
    exact = client.put(
        agent_url(world["mine"]), json={"system_prompt": "a" * AGENT_INSTRUCTIONS_MAX_LENGTH}, headers=world["owner"]
    )
    assert exact.status_code == 200


@pytest.mark.parametrize("who", ["stranger", "loner"])
def test_company_instructions_of_another_company_are_403(client, db, world, who):
    assert client.get(agent_url(world["mine"]), headers=world[who]).status_code == 403
    response = client.put(agent_url(world["mine"]), json={"system_prompt": "golpe"}, headers=world[who])
    assert response.status_code == 403
    db.expire_all()
    assert db.query(Agent).filter(Agent.company_id == world["mine"].id).one().system_prompt != "golpe"
