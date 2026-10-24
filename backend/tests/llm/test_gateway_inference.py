"""GatewayMessagesClient: mapeamento Messages <-> contratos do agente, erros tipados e retry.

O transporte HTTP e trocado por `httpx.MockTransport`; nada sai da maquina.
"""
import json
from typing import Callable

import httpx
import pytest

from app.agent.contracts import MessagesRequest
from app.llm.client import GatewayMessagesClient
from app.llm.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)


class Gateway:
    """Gateway falso: grava os requests e responde com a sequencia de handlers."""

    def __init__(self, *handlers: Callable[[httpx.Request], httpx.Response]):
        self.requests: list[httpx.Request] = []
        self._handlers = list(handlers)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        handler = self._handlers.pop(0) if len(self._handlers) > 1 else self._handlers[0]
        return handler(request)

    def client(self, **kwargs) -> GatewayMessagesClient:
        kwargs.setdefault("base_url", "http://gw.test")
        kwargs.setdefault("api_key", "sk-secret")
        return GatewayMessagesClient(transport=httpx.MockTransport(self), backoff_seconds=0, **kwargs)

    @property
    def last_json(self) -> dict:
        return json.loads(self.requests[-1].content)


def ok(content, *, stop_reason="end_turn", model="claude-sonnet-5.5", output_tokens=7):
    return lambda r: httpx.Response(
        200,
        json={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": content,
            "model": model,
            "stop_reason": stop_reason,
            "usage": {"input_tokens": 3, "output_tokens": output_tokens},
        },
    )


def status(code, text="erro"):
    return lambda r: httpx.Response(code, text=text)


def raises(exc):
    def handler(request):
        raise exc

    return handler


REQUEST = MessagesRequest(
    model="claude-sonnet-5.5",
    system="Voce atende pelo WhatsApp.",
    messages=[{"role": "user", "content": "oi"}],
)


# --- request ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_posts_to_v1_messages_with_anthropic_headers():
    gw = Gateway(ok([{"type": "text", "text": "ola"}]))
    await gw.client(base_url="http://gw.test/").create(REQUEST)

    request = gw.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "http://gw.test/v1/messages"
    assert request.headers["x-api-key"] == "sk-secret"
    assert request.headers["anthropic-version"] == "2023-06-01"


@pytest.mark.asyncio
async def test_request_body_maps_contract_fields_and_effort():
    gw = Gateway(ok([{"type": "text", "text": "ola"}]))
    tool = {"name": "buscar", "description": "d", "input_schema": {"type": "object", "properties": {}}}
    history = [
        {"role": "user", "content": "pizza?"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "buscar", "input": {"q": "pizza"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "3 itens"}]},
    ]
    request = MessagesRequest(
        model="m", system="sys", messages=history, tools=[tool], max_tokens=300, effort="low", temperature=0.2
    )
    await gw.client().create(request)

    assert gw.last_json == {
        "model": "m",
        "system": "sys",
        "messages": history,
        "tools": [tool],
        "max_tokens": 300,
        "temperature": 0.2,
        "output_config": {"effort": "low"},
    }


@pytest.mark.asyncio
async def test_optional_fields_are_omitted_when_unset():
    gw = Gateway(ok([{"type": "text", "text": "ola"}]))
    await gw.client(api_key=None).create(MessagesRequest(model="m", system="", messages=REQUEST.messages))

    assert gw.last_json == {"model": "m", "messages": REQUEST.messages, "max_tokens": 1024}
    assert "x-api-key" not in gw.requests[0].headers


# --- response ----------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_text_response_is_mapped():
    gw = Gateway(ok([{"type": "text", "text": "Ola!"}], output_tokens=5))
    response = await gw.client().create(REQUEST)

    assert response.content == [{"type": "text", "text": "Ola!"}]
    assert response.stop_reason == "end_turn"
    assert response.model == "claude-sonnet-5.5"
    assert response.output_tokens == 5


@pytest.mark.asyncio
async def test_tool_use_response_is_mapped_and_thinking_is_dropped():
    gw = Gateway(
        ok(
            [
                {"type": "thinking", "thinking": "hmm", "signature": "abc"},
                {"type": "text", "text": "Vou buscar."},
                {"type": "tool_use", "id": "toolu_1", "name": "buscar", "input": {"termo": "pizza"}},
            ],
            stop_reason="tool_use",
        )
    )
    response = await gw.client().create(REQUEST)

    assert response.stop_reason == "tool_use"
    assert response.content == [
        {"type": "text", "text": "Vou buscar."},
        {"type": "tool_use", "id": "toolu_1", "name": "buscar", "input": {"termo": "pizza"}},
    ]


# --- erros e retry ------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_retries_rate_limit_then_succeeds():
    gw = Gateway(status(429), status(503), ok([{"type": "text", "text": "ok"}]))
    response = await gw.client().create(REQUEST)

    assert response.content == [{"type": "text", "text": "ok"}]
    assert len(gw.requests) == 3


@pytest.mark.asyncio
async def test_rate_limit_gives_up_after_three_attempts():
    gw = Gateway(status(429, "slow down"))
    with pytest.raises(LLMRateLimitError):
        await gw.client().create(REQUEST)
    assert len(gw.requests) == 3


@pytest.mark.asyncio
async def test_server_error_gives_up_after_three_attempts_with_status():
    gw = Gateway(status(500, "boom"))
    with pytest.raises(LLMProviderError, match="HTTP 500") as info:
        await gw.client().create(REQUEST)
    assert info.value.status_code == 500
    assert len(gw.requests) == 3


@pytest.mark.asyncio
async def test_timeout_is_retried_and_typed():
    gw = Gateway(raises(httpx.ReadTimeout("lento")))
    with pytest.raises(LLMTimeoutError):
        await gw.client().create(REQUEST)
    assert len(gw.requests) == 3


@pytest.mark.asyncio
async def test_client_error_is_not_retried():
    gw = Gateway(status(400, "bad request"))
    with pytest.raises(LLMProviderError, match="HTTP 400"):
        await gw.client().create(REQUEST)
    assert len(gw.requests) == 1


@pytest.mark.asyncio
async def test_error_message_never_contains_api_key():
    gw = Gateway(status(401, "invalid key sk-secret"))
    with pytest.raises(LLMProviderError) as info:
        await gw.client().create(REQUEST)
    assert "sk-secret" not in str(info.value)


# --- resposta malformada: sempre LLMProviderError, nunca KeyError/ValueError/TypeError ---- #

def _json_200(body):
    return lambda r: httpx.Response(200, json=body)


def _msg(content, **extra):
    body = {"content": content, "stop_reason": "end_turn", "model": "m", "usage": {"output_tokens": 1}}
    body.update(extra)
    return body


MALFORMED_BODIES = {
    "json_list": [],
    "json_null": None,
    "content_missing": {"stop_reason": "end_turn"},
    "content_not_list": _msg("texto solto"),
    "block_not_object": _msg(["texto solto"]),
    "tool_use_without_id": _msg([{"type": "tool_use", "name": "buscar", "input": {}}], stop_reason="tool_use"),
    "tool_use_without_name": _msg([{"type": "tool_use", "id": "t1", "input": {}}], stop_reason="tool_use"),
    "tool_use_id_not_string": _msg([{"type": "tool_use", "id": 7, "name": "buscar", "input": {}}]),
    "tool_use_input_not_object": _msg([{"type": "tool_use", "id": "t1", "name": "buscar", "input": "pizza"}]),
    "text_without_text": _msg([{"type": "text"}]),
    "usage_non_numeric": _msg([{"type": "text", "text": "ok"}], usage={"output_tokens": "muitos"}),
    "usage_list": _msg([{"type": "text", "text": "ok"}], usage={"output_tokens": [1]}),
    "usage_not_object": _msg([{"type": "text", "text": "ok"}], usage="1"),
    "stop_reason_not_string": _msg([{"type": "text", "text": "ok"}], stop_reason=5),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("body", MALFORMED_BODIES.values(), ids=MALFORMED_BODIES.keys())
async def test_malformed_json_response_is_a_provider_error_and_not_retried(body):
    gw = Gateway(_json_200(body))
    with pytest.raises(LLMProviderError):
        await gw.client().create(REQUEST)
    assert len(gw.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", ["", "<html>502</html>", "{truncado"])
async def test_non_json_body_is_a_provider_error(raw):
    gw = Gateway(lambda r: httpx.Response(200, text=raw))
    with pytest.raises(LLMProviderError):
        await gw.client().create(REQUEST)


@pytest.mark.asyncio
async def test_missing_usage_and_stop_reason_use_safe_defaults():
    gw = Gateway(_json_200({"content": [{"type": "text", "text": "ok"}]}))
    response = await gw.client().create(REQUEST)

    assert (response.stop_reason, response.output_tokens, response.model) == ("end_turn", 0, REQUEST.model)


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [[], None, {"data": "x"}, {"sem": "data"}, "texto"])
async def test_list_models_malformed_body_is_a_provider_error(body):
    gw = Gateway(_json_200(body))
    with pytest.raises(LLMProviderError):
        await gw.client().list_models()


@pytest.mark.asyncio
async def test_max_attempts_one_disables_retry():
    gw = Gateway(status(503))
    with pytest.raises(LLMProviderError):
        await gw.client(max_attempts=1).create(REQUEST)
    assert len(gw.requests) == 1


# --- probe e listagem de modelos ---------------------------------------------- #

@pytest.mark.asyncio
async def test_probe_uses_messages_with_max_tokens_8():
    gw = Gateway(ok([{"type": "text", "text": "pong"}]))
    result = await gw.client().probe(model="m", effort="low")

    assert gw.last_json["max_tokens"] == 8
    assert gw.last_json["output_config"] == {"effort": "low"}
    assert result["content"] == "pong"
    assert isinstance(result["latency_ms"], int)


@pytest.mark.asyncio
async def test_list_models_reads_v1_models():
    gw = Gateway(lambda r: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]}))
    assert await gw.client().list_models() == ["a", "b"]
    assert str(gw.requests[0].url) == "http://gw.test/v1/models"
    assert gw.requests[0].method == "GET"


@pytest.mark.asyncio
async def test_list_models_404_carries_status_code():
    gw = Gateway(status(404, "nope"))
    with pytest.raises(LLMProviderError) as info:
        await gw.client().list_models()
    assert info.value.status_code == 404


# --- criptografia em repouso -------------------------------------------------- #

def test_secret_roundtrip_and_ciphertext_hides_plaintext():
    from app.core.crypto import decrypt_secret, encrypt_secret

    token = encrypt_secret("sk-abc")
    assert "sk-abc" not in token and decrypt_secret(token) == "sk-abc"


def test_tokens_derived_from_secret_key_no_longer_open():
    """Tokens feitos com a SECRET_KEY (SHA-256 ou HKDF) NAO abrem: so a GATEWAY_ENCRYPTION_KEY decifra."""
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    from app.core.config import settings
    from app.core.crypto import SecretDecryptionError, _fernet_for, decrypt_secret

    sha256 = Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest()))
    hkdf = _fernet_for(settings.SECRET_KEY)
    for old in (sha256, hkdf):
        with pytest.raises(SecretDecryptionError):
            decrypt_secret(old.encrypt(b"sk-old").decode())
