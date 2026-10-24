"""O núcleo (`app/agent`) não conhece ramo (ADR 0004).

Dois testes: (1) nenhum arquivo importa Pack nem model de catálogo e pedidos; (2) o texto que o modelo vê vindo do
núcleo (Tools do núcleo, prompt base e prompt do Summary) não cita nada de catálogo e pedidos. Comentário e docstring
não entram: quem lê o código pode citar um exemplo, o modelo não.
"""

import ast
import json
import re
from pathlib import Path

import pytest

from app.agent.core_tools import core_tools
from app.agent.memory import _SUMMARY_SYSTEM
from app.agent.prompts import build_system_prompt

CORE_DIR = Path(__file__).resolve().parents[2] / "app" / "agent"
APP_DIR = CORE_DIR.parent
CORE_FILES = sorted(CORE_DIR.rglob("*.py"))

BUSINESS_MODELS = frozenset(
    {"DeliveryZone", "PaymentRecord", "CustomerOrder", "CustomerOrderItem", "MenuCatalog", "MenuCategory", "MenuItem"}
)
BUSINESS_MODEL_MODULES = ("app.models.order", "app.models.catalog")
BUSINESS_TERMS = re.compile(
    r"pizza|card[aá]pio|\bpix\b|pedido|\border\b|entrega|delivery|pagamento|payment|cupom|catalog|taxa|recap",
    re.IGNORECASE,
)


def _package_of(path: Path) -> str:
    return ".".join(("app", *path.relative_to(APP_DIR).parent.parts))


def _dotted_imports(source: str, package: str) -> list[str]:
    """Nome absoluto de tudo que o código importa, resolvendo imports relativos (`from ..packs import x`)."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - (node.level - 1)]
                base = ".".join([*parts, *([node.module] if node.module else [])])
            found.append(base)
            found.extend(f"{base}.{alias.name}" for alias in node.names)
    return found


def _referenced_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }


def _under(name: str, module: str) -> bool:
    return name == module or name.startswith(f"{module}.")


def test_core_files_were_found():
    assert CORE_DIR / "executor.py" in CORE_FILES and len(CORE_FILES) > 10


@pytest.mark.parametrize("path", CORE_FILES, ids=lambda p: p.name)
def test_core_imports_nothing_from_packs(path):
    assert [name for name in _dotted_imports(path.read_text(encoding="utf-8"), _package_of(path)) if _under(name, "app.packs")] == []


@pytest.mark.parametrize("path", CORE_FILES, ids=lambda p: p.name)
def test_core_imports_no_catalog_or_order_models(path):
    names = _dotted_imports(path.read_text(encoding="utf-8"), _package_of(path))
    by_module = [name for name in names if any(_under(name, m) for m in BUSINESS_MODEL_MODULES)]
    by_name = sorted(_referenced_names(path) & BUSINESS_MODELS)
    assert by_module == [] and by_name == []


def test_import_scanner_catches_the_known_gaps():
    """O scanner enxerga `from app.models import order` e os imports relativos `from ..packs import x`."""
    source = "from app.models import order\nfrom ..packs import registry\nfrom .. import packs\nimport app.packs.x\n"

    names = _dotted_imports(source, "app.agent")

    assert {"app.models.order", "app.packs.registry", "app.packs", "app.packs.x"} <= set(names)


def _model_visible_core_text() -> str:
    tools = [
        {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema}
        for tool in core_tools()
    ]
    base_prompt = build_system_prompt(company_name="Empresa X", packs=[], ctx=None)
    return "\n".join([json.dumps(tools, ensure_ascii=False), base_prompt, _SUMMARY_SYSTEM])


def test_text_the_model_sees_from_the_core_has_no_catalog_or_order_terms():
    hits = sorted({match.group(0).lower() for match in BUSINESS_TERMS.finditer(_model_visible_core_text())})
    assert hits == []
