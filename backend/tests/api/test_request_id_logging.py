"""Request id e logs JSON (#94): `X-Request-ID` válido é aceito, o inválido é trocado, e o log de erro leva `level`,
`request_id` e o traceback."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

HEADER = "X-Request-ID"


@pytest.fixture
def anon():
    return TestClient(app, raise_server_exceptions=False)


def _logs(capsys) -> list[dict]:
    lines = [line for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    return [json.loads(line) for line in lines]


def test_a_valid_request_id_is_kept(anon):
    assert anon.get("/health", headers={HEADER: "abc-123_X.y"}).headers[HEADER] == "abc-123_X.y"


@pytest.mark.parametrize("bad", ["com espaco", "x" * 65, "a;b", "aspas\"", ""])
def test_an_invalid_request_id_is_replaced(anon, bad):
    got = anon.get("/health", headers={HEADER: bad}).headers[HEADER]
    assert got != bad and len(got) == 32


def test_each_request_without_id_gets_its_own(anon):
    assert anon.get("/health").headers[HEADER] != anon.get("/health").headers[HEADER]


def test_cors_exposes_the_request_id_to_the_browser(anon):
    response = anon.get("/health", headers={"Origin": "http://localhost:3000"})

    assert HEADER in response.headers["access-control-expose-headers"]


def test_the_origin_guard_rejection_carries_the_id(anon):
    response = anon.post("/api/v1/auth/login", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403 and response.headers[HEADER]


def test_error_log_is_json_with_level_request_id_and_traceback(anon, monkeypatch, capsys):
    def boom(**_):
        raise RuntimeError("falha de teste")

    monkeypatch.setattr("app.main.HealthResponse", boom)

    response = anon.get("/health", headers={HEADER: "req-erro-1"})

    assert response.status_code == 500 and response.headers[HEADER] == "req-erro-1"
    [entry] = [e for e in _logs(capsys) if e.get("level") == "error"]
    assert entry["request_id"] == "req-erro-1"
    assert "Traceback" in entry["exception"] and "RuntimeError: falha de teste" in entry["exception"]


def test_the_request_id_does_not_leak_into_the_next_request(anon, capsys):
    anon.get("/health", headers={HEADER: "req-a"})
    capsys.readouterr()

    anon.get("/health", headers={HEADER: "req-b"})

    assert all(e.get("request_id") != "req-a" for e in _logs(capsys))
