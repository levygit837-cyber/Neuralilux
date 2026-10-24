"""Contrato: toda rota que devolve JSON declara um `response_model` tipado (nada de dict solto)."""
from app.main import app

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _typed(schema: dict) -> bool:
    if "$ref" in schema:
        return True
    if schema.get("type") == "array":
        return _typed(schema.get("items") or {})
    if schema.get("properties"):
        return True
    return any(_typed(option) for key in ("anyOf", "oneOf", "allOf") for option in schema.get(key, []))


def test_every_json_response_has_a_typed_schema():
    violations = []
    for path, operations in app.openapi()["paths"].items():
        for method, operation in operations.items():
            if method not in HTTP_METHODS:
                continue
            for code, response in operation["responses"].items():
                if not code.startswith("2") or code == "204":
                    continue
                schema = response.get("content", {}).get("application/json", {}).get("schema")
                if schema is None or not _typed(schema):
                    violations.append(f"{method.upper()} {path}")
    assert not violations, "Rotas sem response_model tipado:\n" + "\n".join(sorted(set(violations)))
