def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["version"]


def _status_codes_in_fresh_process(env: dict[str, str]) -> dict[str, int]:
    """Importa `app.main` num processo novo (o `docs_url` é decidido na importação) e consulta as rotas."""
    import json
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    code = (
        "import json; from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); "
        "print(json.dumps({p: c.get(p).status_code for p in ('/docs', '/redoc')}))"
    )
    backend = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory() as tmp:
        base = {k: v for k, v in os.environ.items() if k not in ("ENVIRONMENT", "SECRET_KEY")}
        base["DATABASE_URL"] = f"sqlite:///{tmp}/docs.db"
        base["PYTHONPATH"] = str(backend)
        # cwd fora de backend/: o Settings não lê o backend/.env de quem roda a suíte.
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=tmp, env={**base, **env}, capture_output=True, text=True, check=True
        )
    return json.loads(result.stdout.splitlines()[-1])


def test_docs_are_hidden_without_explicit_development():
    strong = {"SECRET_KEY": "s" * 48, "EVOLUTION_WEBHOOK_TOKEN": "w" * 32, "GATEWAY_ENCRYPTION_KEY": "g" * 48}
    assert _status_codes_in_fresh_process(strong) == {"/docs": 404, "/redoc": 404}


def test_docs_are_served_in_explicit_development():
    assert _status_codes_in_fresh_process({"ENVIRONMENT": "development"}) == {"/docs": 200, "/redoc": 200}
