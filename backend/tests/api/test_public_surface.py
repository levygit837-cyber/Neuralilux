"""Superfície pública (#85): rate limit por IP em /auth/login e /auth/register, cadastro público fechado por padrão."""
import time as real_time

import pytest
from starlette.requests import Request

from app.core import rate_limit
from app.core.config import settings
from app.models import User
from tests.access_helpers import make_user

LOGIN = "/api/v1/auth/login"
REGISTER = "/api/v1/auth/register"


class _Clock:
    """Relógio do fakeredis (ele expira chaves por `time.time()`): o teste avança a janela sem dormir."""

    def __init__(self):
        self.now = real_time.time()

    def time(self):
        return self.now

    def __getattr__(self, name):
        return getattr(real_time, name)


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr("fakeredis._socket._base.time", fake)
    return fake


def _login(client, password="errada"):
    return client.post(LOGIN, data={"username": "alguem@example.com", "password": password})


def _payload(email: str) -> dict:
    return {"email": email, "password": "testpass123", "full_name": "Novo"}


def _request(peer: str | None, forwarded: str | list[str] | None = None) -> Request:
    """`forwarded` em lista vira uma linha de cabeçalho por item, como o HAProxy faz ao anexar."""
    lines = [forwarded] if isinstance(forwarded, str) else forwarded or []
    headers = [(b"x-forwarded-for", line.encode()) for line in lines]
    return Request({"type": "http", "headers": headers, "client": (peer, 5000) if peer else None})


# --- login: 429 + Retry-After, janela que vira ------------------------------------------------------------


def test_login_over_the_limit_is_429_with_retry_after(client, monkeypatch, clock):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)

    assert [_login(client).status_code for _ in range(3)] == [401, 401, 401]
    blocked = _login(client)

    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert "errada" not in blocked.text


def test_blocked_login_does_not_check_the_password(client, db, monkeypatch, clock):
    make_user(client, db, "alguem@example.com")  # o login do helper já conta uma tentativa
    clock.now += settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS + 1
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 2)

    assert _login(client).status_code == 401
    assert _login(client, "testpass123").status_code == 200
    assert _login(client, "testpass123").status_code == 429  # a senha certa também espera a janela


def test_retry_after_counts_down_and_the_window_resets(client, monkeypatch, clock):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)
    _login(client), _login(client)
    first = int(_login(client).headers["Retry-After"])

    clock.now += 30
    later = _login(client)
    assert later.status_code == 429
    assert int(later.headers["Retry-After"]) < first

    clock.now += 31  # a janela de 60 s virou: o contador recomeça
    assert _login(client).status_code == 401


# --- cadastro: fechado por padrão, rate limit, superusuário ----------------------------------------------


def test_registration_is_closed_by_default(monkeypatch):
    # O fixture autouse abre o cadastro para a suíte; o padrão do código é fechado.
    from app.core.config import Settings

    assert Settings.model_fields["ALLOW_PUBLIC_REGISTRATION"].default is False


def test_anonymous_registration_is_refused_when_closed(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", False)

    response = client.post(REGISTER, json=_payload("novo@example.com"))

    assert response.status_code == 403
    assert response.json()["detail"] == "Public registration is disabled"
    assert db.query(User).filter(User.email == "novo@example.com").count() == 0


def test_anonymous_registration_works_when_open(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", True)

    assert client.post(REGISTER, json=_payload("novo@example.com")).status_code == 201
    assert db.query(User).filter(User.email == "novo@example.com").count() == 1


def test_regular_user_cannot_register_others_when_closed(client, db, monkeypatch):
    comum = make_user(client, db, "comum@example.com")
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", False)

    response = client.post(REGISTER, json=_payload("outro@example.com"), headers=comum)

    assert response.status_code == 403


def test_superuser_registers_when_closed_and_is_not_throttled(client, db, monkeypatch, clock):
    admin = make_user(client, db, "admin@example.com", superuser=True)
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", False)
    monkeypatch.setattr(settings, "REGISTER_RATE_LIMIT_ATTEMPTS", 1)

    codes = [client.post(REGISTER, json=_payload(f"u{i}@example.com"), headers=admin).status_code for i in range(3)]

    assert codes == [201, 201, 201]


def test_register_over_the_limit_is_429_with_retry_after(client, monkeypatch, clock):
    monkeypatch.setattr(settings, "REGISTER_RATE_LIMIT_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "REGISTER_RATE_LIMIT_WINDOW_SECONDS", 3600)

    assert [client.post(REGISTER, json=_payload(f"u{i}@example.com")).status_code for i in range(2)] == [201, 201]
    blocked = client.post(REGISTER, json=_payload("u3@example.com"))

    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 3600


def test_closed_registration_still_counts_attempts(client, monkeypatch, clock):
    monkeypatch.setattr(settings, "ALLOW_PUBLIC_REGISTRATION", False)
    monkeypatch.setattr(settings, "REGISTER_RATE_LIMIT_ATTEMPTS", 2)

    codes = [client.post(REGISTER, json=_payload(f"u{i}@example.com")).status_code for i in range(3)]

    assert codes == [403, 403, 429]


def test_login_and_register_have_separate_counters(client, monkeypatch, clock):
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_ATTEMPTS", 1)
    _login(client)
    assert _login(client).status_code == 429

    assert client.post(REGISTER, json=_payload("novo@example.com")).status_code == 201


# --- Redis fora do ar: falha fechada ----------------------------------------------------------------------


def test_login_fails_closed_with_503_when_redis_is_down(client, db, monkeypatch):
    make_user(client, db, "alguem@example.com")

    class Broken:
        def pipeline(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(rate_limit, "_new_client", lambda: Broken())

    response = _login(client, "testpass123")

    assert response.status_code == 503
    assert "access_token" not in response.text
    assert "redis" not in response.text.lower()


def test_register_fails_closed_with_503_when_redis_is_down(client, db, monkeypatch):
    class Broken:
        def pipeline(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(rate_limit, "_new_client", lambda: Broken())

    assert client.post(REGISTER, json=_payload("novo@example.com")).status_code == 503
    assert db.query(User).filter(User.email == "novo@example.com").count() == 0


def test_superuser_registers_even_if_redis_is_down(client, db, monkeypatch):
    admin = make_user(client, db, "admin@example.com", superuser=True)

    class Broken:
        def pipeline(self, *args, **kwargs):
            raise ConnectionError("redis down")

    monkeypatch.setattr(rate_limit, "_new_client", lambda: Broken())
    monkeypatch.setattr(rate_limit, "_redis", None)

    assert client.post(REGISTER, json=_payload("novo@example.com"), headers=admin).status_code == 201


@pytest.mark.asyncio
async def test_stuck_redis_times_out_instead_of_hanging(monkeypatch):
    import asyncio

    class Stuck:
        def pipeline(self, *args, **kwargs):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def incr(self, *a, **k): ...
        def expire(self, *a, **k): ...
        def ttl(self, *a, **k): ...

        async def execute(self):
            await asyncio.sleep(30)

    monkeypatch.setattr(rate_limit, "_new_client", lambda: Stuck())
    monkeypatch.setattr(rate_limit, "_redis", None)
    monkeypatch.setattr(rate_limit, "_redis_loop", None)
    monkeypatch.setattr(settings, "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setattr(settings, "REDIS_SOCKET_TIMEOUT_SECONDS", 0.05)

    started = real_time.monotonic()
    with pytest.raises(Exception) as caught:
        await rate_limit.enforce_rate_limit(_request("10.0.0.1"), "login", 5, 60)

    assert caught.value.status_code == 503
    assert real_time.monotonic() - started < 2


# --- IP do cliente atrás de proxy -------------------------------------------------------------------------


def test_forwarded_header_is_ignored_without_trusted_proxies(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", [])

    assert rate_limit.client_ip(_request("203.0.113.9", "198.51.100.7")) == "203.0.113.9"


def test_forwarded_header_is_ignored_from_an_untrusted_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])

    assert rate_limit.client_ip(_request("203.0.113.9", "198.51.100.7")) == "203.0.113.9"


def test_forwarded_header_is_honored_from_a_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])

    assert rate_limit.client_ip(_request("10.1.2.3", "198.51.100.7")) == "198.51.100.7"


def test_a_spoofed_leftmost_hop_does_not_pick_the_key(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])

    # O cliente mandou "1.1.1.1"; o proxy confiável anexou o IP real (198.51.100.7) à direita.
    assert rate_limit.client_ip(_request("10.1.2.3", "1.1.1.1, 198.51.100.7")) == "198.51.100.7"
    assert rate_limit.client_ip(_request("10.1.2.3", "1.1.1.1, 198.51.100.7, 10.9.9.9")) == "198.51.100.7"


def test_garbage_in_the_forwarded_header_falls_back_to_the_peer(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])

    assert rate_limit.client_ip(_request("10.1.2.3", "nao-e-ip")) == "10.1.2.3"
    assert rate_limit.client_ip(_request("10.1.2.3")) == "10.1.2.3"


def test_missing_peer_is_a_single_shared_key(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", [])

    assert rate_limit.client_ip(_request(None)) == "unknown"


@pytest.mark.asyncio
async def test_each_client_ip_has_its_own_counter(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])

    for _ in range(2):
        await rate_limit.enforce_rate_limit(_request("10.0.0.1", "198.51.100.1"), "login", 2, 60)
    with pytest.raises(Exception) as caught:
        await rate_limit.enforce_rate_limit(_request("10.0.0.1", "198.51.100.1"), "login", 2, 60)
    assert caught.value.status_code == 429

    await rate_limit.enforce_rate_limit(_request("10.0.0.1", "198.51.100.2"), "login", 2, 60)


def test_trusted_proxies_rejects_a_value_that_is_not_a_network(monkeypatch):
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(TRUSTED_PROXIES=["nao-e-rede"])


# --- X-Forwarded-For em várias linhas, IPv6 por /64, defaults, cliente descartado ------------------------------


def test_forwarded_header_split_over_several_lines_cannot_forge_the_ip(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])

    # Linha 1 é do cliente (forjada); o proxy confiável anexou a linha 2 com o IP real.
    assert rate_limit.client_ip(_request("10.1.2.3", ["1.1.1.1", "198.51.100.7"])) == "198.51.100.7"
    assert rate_limit.client_ip(_request("10.1.2.3", ["1.1.1.1, 2.2.2.2", "198.51.100.7, 10.9.9.9"])) == "198.51.100.7"


@pytest.mark.asyncio
async def test_rotating_a_forged_first_line_does_not_escape_the_counter(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", ["10.0.0.0/8"])

    for forged in ("1.1.1.1", "2.2.2.2"):
        await rate_limit.enforce_rate_limit(_request("10.0.0.1", [forged, "198.51.100.7"]), "login", 2, 60)
    with pytest.raises(Exception) as caught:
        await rate_limit.enforce_rate_limit(_request("10.0.0.1", ["3.3.3.3", "198.51.100.7"]), "login", 2, 60)

    assert caught.value.status_code == 429


def test_ipv6_clients_are_counted_by_their_64_prefix():
    same_prefix = {rate_limit._bucket("2001:db8:1:2::1"), rate_limit._bucket("2001:db8:1:2:aaaa:bbbb:cccc:dddd")}
    assert same_prefix == {"2001:db8:1:2::/64"}
    assert rate_limit._bucket("2001:db8:1:3::1") != rate_limit._bucket("2001:db8:1:2::1")
    assert rate_limit._bucket("::ffff:203.0.113.9") == "203.0.113.9"  # IPv4 mapeado conta como o IPv4
    assert rate_limit._bucket("203.0.113.9") == "203.0.113.9"
    assert rate_limit._bucket("unknown") == "unknown"


@pytest.mark.asyncio
async def test_changing_the_ipv6_suffix_does_not_reset_the_counter():
    for suffix in ("1", "2"):
        await rate_limit.enforce_rate_limit(_request(f"2001:db8:1:2::{suffix}"), "login", 2, 60)
    with pytest.raises(Exception) as caught:
        await rate_limit.enforce_rate_limit(_request("2001:db8:1:2:dead:beef:0:3"), "login", 2, 60)

    assert caught.value.status_code == 429
    await rate_limit.enforce_rate_limit(_request("2001:db8:1:9::1"), "login", 2, 60)  # outro /64 tem contador próprio


def test_shipped_defaults_of_the_limits():
    from app.core.config import Settings

    fields = Settings.model_fields
    assert (fields["LOGIN_RATE_LIMIT_ATTEMPTS"].default, fields["LOGIN_RATE_LIMIT_WINDOW_SECONDS"].default) == (10, 60)
    assert (fields["REGISTER_RATE_LIMIT_ATTEMPTS"].default, fields["REGISTER_RATE_LIMIT_WINDOW_SECONDS"].default) == (
        5,
        3600,
    )
    assert fields["TRUSTED_PROXIES"].default == []


@pytest.mark.asyncio
async def test_failed_client_is_closed_in_background_not_leaked(monkeypatch):
    import asyncio

    class Broken:
        closed = False

        def pipeline(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def aclose(self):
            Broken.closed = True

    monkeypatch.setattr(rate_limit, "_new_client", lambda: Broken())
    monkeypatch.setattr(rate_limit, "_redis", None)
    monkeypatch.setattr(rate_limit, "_redis_loop", None)

    with pytest.raises(Exception) as caught:
        await rate_limit.enforce_rate_limit(_request("10.0.0.1"), "login", 5, 60)
    assert caught.value.status_code == 503
    await asyncio.gather(*rate_limit._closing)

    assert Broken.closed is True
    assert rate_limit._redis is None and not rate_limit._closing


@pytest.mark.asyncio
async def test_a_close_that_hangs_never_blocks_the_503(monkeypatch):
    import asyncio

    class Hung:
        def pipeline(self, *args, **kwargs):
            raise ConnectionError("redis down")

        async def aclose(self):
            await asyncio.sleep(30)

    monkeypatch.setattr(rate_limit, "_new_client", lambda: Hung())
    monkeypatch.setattr(rate_limit, "_redis", None)
    monkeypatch.setattr(rate_limit, "_redis_loop", None)
    monkeypatch.setattr(settings, "REDIS_SOCKET_TIMEOUT_SECONDS", 0.05)

    started = real_time.monotonic()
    with pytest.raises(Exception) as caught:
        await rate_limit.enforce_rate_limit(_request("10.0.0.1"), "login", 5, 60)
    assert caught.value.status_code == 503
    assert real_time.monotonic() - started < 1  # o fechamento roda em background

    await asyncio.gather(*rate_limit._closing)  # e o teto de fechamento o encerra
    assert not rate_limit._closing
