"""O núcleo (`app/agent`) não conhece ramo (ADR 0004): nem imports de Pack e dos models de catálogo e pedidos,
nem termos do negócio. Quem sabe de entrega, Pix e cardápio é o Pack (`app/packs`)."""

import ast
import re
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).resolve().parents[2] / "app" / "agent"
CORE_FILES = sorted(CORE_DIR.rglob("*.py"))

# Models de catálogo e pedidos: o núcleo não os importa nem por `app.models` nem pelo módulo.
BUSINESS_MODELS = frozenset(
    {"DeliveryZone", "PaymentRecord", "CustomerOrder", "CustomerOrderItem", "MenuCatalog", "MenuCategory", "MenuItem"}
)
BUSINESS_MODEL_MODULES = ("app.models.order", "app.models.catalog")
BUSINESS_TERMS = re.compile(
    r"pizza|card[aá]pio|\bpix\b|pedido|\border\b|cupom|catalog_orders|taxa de entrega|taxas_entrega|"
    r"formas?_pagamento|chave_pix|pedido_minimo",
    re.IGNORECASE,
)


def _imports(path: Path) -> list[tuple[str, str | None]]:
    """(módulo, nome importado) de cada import; `None` no nome quando é `import x`."""
    found: list[tuple[str, str | None]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.extend((node.module, alias.name) for alias in node.names)
        elif isinstance(node, ast.Import):
            found.extend((alias.name, None) for alias in node.names)
    return found


def test_core_files_were_found():
    assert CORE_DIR / "executor.py" in CORE_FILES and len(CORE_FILES) > 10


@pytest.mark.parametrize("path", CORE_FILES, ids=lambda p: p.name)
def test_core_imports_nothing_from_packs(path):
    offending = [module for module, _ in _imports(path) if module == "app.packs" or module.startswith("app.packs.")]
    assert offending == []


@pytest.mark.parametrize("path", CORE_FILES, ids=lambda p: p.name)
def test_core_imports_no_catalog_or_order_models(path):
    offending = [
        f"{module}.{name}"
        for module, name in _imports(path)
        if module.startswith(BUSINESS_MODEL_MODULES) or (name in BUSINESS_MODELS)
    ]
    assert offending == []


@pytest.mark.parametrize("path", CORE_FILES, ids=lambda p: p.name)
def test_core_has_no_catalog_or_order_terms(path):
    hits = [
        f"{number}: {line.strip()}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if BUSINESS_TERMS.search(line)
    ]
    assert hits == []
