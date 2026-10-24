"""Retry do Gateway: orçamento por Turn, jitter e `Retry-After` em 429/503/529. 4xx continua sem retry.

O transporte é `httpx.MockTransport` e o sono é falso: o teste vê quanto o cliente quis esperar sem esperar.
"""
import httpx
import pytest

from app.agent.contracts import MessagesRequest
from app.core.config import settings
from app.llm.client import GatewayMessagesClient
from app.llm.errors import LLMProviderError, LLMRateLimitError
from app.llm.retry import RetryBudget
from tests.llm.test_gateway_inference import Gateway, ok, status

OK = ok([{"type": "text", "text": "ok"}])


def _request(budget: RetryBudget | None = None) -> MessagesRequest:
    return MessagesRequest(model="m", system="", messages=[{"role": "user", "content": "oi"}], retry_budget=budget)


def _with_header(code: int, **headers: str):
    return lambda r: httpx.Response(code, text="erro", headers=headers)


class Sleeps:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


def _client(gw: Gateway, sleeps: Sleeps, **kwargs):
    # `uniform` no piso: o jitter some e sobra só o que o cliente é obrigado a esperar.
    return gw.client(sleep=sleeps, uniform=lambda low, high: low, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [429, 503, 529])
async def test_retry_after_is_awaited_for_the_indicated_time(code):
    gw = Gateway(_with_header(code, **{"Retry-After": "7"}), OK)
    sleeps = Sleeps()

    response = await _client(gw, sleeps).create(_request(RetryBudget(retries=2, wait_seconds=30)))

    assert response.content == [{"type": "text", "text": "ok"}]
    assert sleeps.delays == [7.0]
    assert len(gw.requests) == 2


@pytest.mark.asyncio
async def test_retry_after_as_http_date_is_honoured():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    when = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=9), usegmt=True)
    gw = Gateway(_with_header(429, **{"Retry-After": when}), OK)
    sleeps = Sleeps()

    await _client(gw, sleeps).create(_request(RetryBudget(retries=2, wait_seconds=30)))

    assert 7.0 <= sleeps.delays[0] <= 9.0


@pytest.mark.asyncio
async def test_retry_after_longer_than_what_is_left_of_the_turn_budget_gives_up_without_waiting():
    gw = Gateway(_with_header(429, **{"Retry-After": "120"}), OK)
    sleeps = Sleeps()

    with pytest.raises(LLMRateLimitError):
        await _client(gw, sleeps).create(_request(RetryBudget(retries=2, wait_seconds=20)))

    assert sleeps.delays == []
    assert len(gw.requests) == 1


@pytest.mark.asyncio
async def test_the_budget_belongs_to_the_turn_not_to_each_call():
    budget = RetryBudget(retries=1, wait_seconds=30)
    sleeps = Sleeps()

    first = Gateway(status(503), OK)
    await _client(first, sleeps).create(_request(budget))  # gasta o único retry do Turn
    assert len(first.requests) == 2

    second = Gateway(status(503), OK)
    with pytest.raises(LLMProviderError, match="HTTP 503"):
        await _client(second, sleeps).create(_request(budget))  # outra chamada do mesmo Turn: sem retry
    assert len(second.requests) == 1


@pytest.mark.asyncio
async def test_waits_spent_on_retries_come_out_of_the_turn_budget():
    budget = RetryBudget(retries=5, wait_seconds=10)
    sleeps = Sleeps()
    gw = Gateway(_with_header(429, **{"Retry-After": "6"}), OK)
    await _client(gw, sleeps).create(_request(budget))
    assert budget.wait_seconds == 4

    gw = Gateway(_with_header(429, **{"Retry-After": "6"}), OK)
    with pytest.raises(LLMRateLimitError):  # 6 s pedidos, restam 4
        await _client(gw, sleeps).create(_request(budget))
    assert sleeps.delays == [6.0]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [400, 401, 404, 422])
async def test_client_errors_are_never_retried(code):
    gw = Gateway(_with_header(code, **{"Retry-After": "1"}), OK)
    sleeps = Sleeps()

    with pytest.raises(LLMProviderError):
        await _client(gw, sleeps).create(_request(RetryBudget(retries=5, wait_seconds=60)))

    assert len(gw.requests) == 1
    assert sleeps.delays == []


@pytest.mark.asyncio
async def test_without_retry_after_the_wait_is_a_jitter_below_the_exponential_cap():
    gw = Gateway(status(503), status(503), OK)
    sleeps = Sleeps()
    client = GatewayMessagesClient(
        "http://gw.test", transport=httpx.MockTransport(gw), sleep=sleeps, uniform=lambda low, high: high
    )  # backoff_seconds padrão: 1 s

    await client.create(_request(RetryBudget(retries=2, wait_seconds=30)))

    assert sleeps.delays == [1.0, 2.0]  # teto de cada tentativa: 1 s, 2 s; o jitter sorteia entre 0 e o teto


@pytest.mark.asyncio
async def test_call_without_a_turn_budget_gets_its_own_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "TURN_RETRY_BUDGET", 1)
    gw = Gateway(status(503))
    with pytest.raises(LLMProviderError):
        await _client(gw, Sleeps()).create(_request())
    assert len(gw.requests) == 2  # 1 tentativa + 1 retry, apesar de max_attempts=3
