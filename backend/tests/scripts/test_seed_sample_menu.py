"""scripts/seed_data.py: num banco sem dados o seed cria a Company de teste com o cardápio de exemplo versionado."""
import importlib.util
import json
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.models import Company, DeliveryZone, MenuCatalog, MenuItem, User

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _seed_module():
    spec = importlib.util.spec_from_file_location("seed_data_script", _SCRIPTS / "seed_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_on_an_empty_database_imports_the_versioned_sample_menu(db, monkeypatch):
    seed = _seed_module()
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=db.get_bind()))
    expected = {
        item["name"]
        for category in json.loads((_SCRIPTS / "sample_menu.json").read_text(encoding="utf-8"))["categories"]
        for item in category["items"]
    }

    seed.main()
    db.expire_all()

    company = db.query(Company).filter(Company.name == "Empresa Teste").one()
    catalog = db.query(MenuCatalog).filter(MenuCatalog.company_id == company.id).one()
    assert {item.name for item in db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id)} == expected
    assert db.query(User).filter(User.email == "usuario@teste.com").one().company_id == company.id
    assert db.query(DeliveryZone).filter(DeliveryZone.company_id == company.id).count() == 1


def test_seeding_twice_does_not_duplicate_the_sample_menu(db, monkeypatch):
    seed = _seed_module()
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=db.get_bind()))

    seed.main()
    first = db.query(MenuItem).count()
    seed.main()

    assert db.query(MenuItem).count() == first
