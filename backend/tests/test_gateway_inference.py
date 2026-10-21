"""Gateway OpenAI-compatible: normalizacao de mensagens/tools/respostas, streaming, registry e fallback."""
import json
import types
from typing import Any, Callable, Dict, List

import httpx
import pytest

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.models import GatewayAssignment, GatewayModel, InferenceGateway
from app.services import gateway_registry
from app.services.gateway_inference_service import (
    GatewayInferenceService,
    _TagParser,
    parse_assistant_message,
    to_openai_messages,
    to_openai_tools,
)
from app.services.inference_service import (
    FallbackInferenceService,
    InferenceRateLimitError,
    InferenceServiceError,
)
from tests.conftest import TestingSessionLocal


def _sse(*chunks: Dict[str, Any]) -> str:
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


def _delta(**delta: Any) -> Dict[str, Any]:
    return {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]}


@pytest.fixture
def http(monkeypatch):
    """Troca o transporte HTTP do cliente; devolve a lista de requests recebidos."""
    seen: List[httpx.Request] = []
    handler_box: Dict[str, Callable[[httpx.Request], httpx.Response]] = {}
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        def handle(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler_box["fn"](request)

        kwargs["transport"] = httpx.MockTransport(handle)
        return real_client(*args, **kwargs)

    # Proxy local: patchar `httpx.AsyncClient` globalmente quebra SDKs que herdam dessa classe (google-genai).
    scoped_httpx = types.SimpleNamespace(**{name: getattr(httpx, name) for name in dir(httpx)})
    scoped_httpx.AsyncClient = factory
    monkeypatch.setattr("app.services.gateway_inference_service.httpx", scoped_httpx)
    seen_box = type("Http", (), {})()
    seen_box.requests = seen
    seen_box.respond = lambda fn: handler_box.__setitem__("fn", fn)
    return seen_box


def _service(**kwargs) -> GatewayInferenceService:
    return GatewayInferenceService(
        base_url="http://gw.test/v1", model="m1", gateway_name="gw", **kwargs
    )


# --- normalizacao de requisicao ---------------------------------------------- #

def test_gemini_parts_roundtrip_becomes_openai_tool_messages():
    messages = [
        {"role": "user", "parts": [{"text": "horario?"}]},
        {"role": "model", "parts": [{"functionCall": {"name": "horario_tool", "args": {"company_id": "c1"}}}]},
        {"role": "user", "parts": [{"functionResponse": {"name": "horario_tool", "response": {"result": "18h"}}}]},
    ]
    out = to_openai_messages(messages, system_prompt="sys")

    assert out[0] == {"role": "system", "content": "sys"}
    assistant, tool = out[2], out[3]
    call = assistant["tool_calls"][0]
    assert json.loads(call["function"]["arguments"]) == {"company_id": "c1"}
    assert tool["role"] == "tool" and tool["tool_call_id"] == call["id"]  # id casado pelo nome


def test_gemini_function_declarations_become_openai_tools_with_lowercase_types():
    tools = [{"function_declarations": [{
        "name": "pedido_tool",
        "description": "d",
        "parameters": {"type": "OBJECT", "properties": {"qtd": {"type": "INTEGER"}}, "required": ["qtd"]},
    }]}]
    [tool] = to_openai_tools(tools)

    assert tool["type"] == "function"
    assert tool["function"]["parameters"]["type"] == "object"
    assert tool["function"]["parameters"]["properties"]["qtd"]["type"] == "integer"


def test_openai_assistant_tool_calls_with_dict_arguments_are_serialized():
    out = to_openai_messages([
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "x", "function": {"name": "t", "arguments": {"a": 1}}}]},
    ])
    assert out[0]["tool_calls"][0]["function"]["arguments"] == '{"a": 1}'


# --- normalizacao de resposta ------------------------------------------------ #

def test_tag_parser_never_leaks_tags_split_across_chunks():
    parser = _TagParser(detect_tool_calls=True)
    out = []
    for piece in ["ola <thi", "nk>pensando</th", "ink>resposta <tool_", 'call>{"name":"t",', '"arguments":{}}</tool_call>']:
        out += parser.feed(piece)
    out += parser.feed("", final=True)

    assert "".join(t for k, t in out if k == "thinking") == "pensando"
    assert "".join(t for k, t in out if k == "response") == "ola resposta "
    assert parser.tool_blocks == ['{"name":"t","arguments":{}}']


def test_parse_message_keeps_reasoning_separate_and_decodes_arguments():
    thinking, content, calls = parse_assistant_message(
        {"content": "ok", "reasoning_content": "raciocinio",
         "tool_calls": [{"id": "c1", "function": {"name": "horario_tool", "arguments": '{"company_id": "abc"}'}}]},
        detect_text_tools=True,
    )
    assert (thinking, content) == ("raciocinio", "ok")
    assert calls == [{"id": "c1", "type": "function",
                      "function": {"name": "horario_tool", "arguments": {"company_id": "abc"}}}]


def test_parse_message_reads_text_tool_call_when_model_has_no_native_support():
    _, content, calls = parse_assistant_message(
        {"content": 'vou consultar <tool_call>{"name": "cardapio_tool", "arguments": {"query": "pizza"}}</tool_call>'},
        detect_text_tools=True,
    )
    assert content == "vou consultar"
    assert calls[0]["function"] == {"name": "cardapio_tool", "arguments": {"query": "pizza"}}


def test_malformed_arguments_become_empty_dict_instead_of_raising():
    _, _, calls = parse_assistant_message(
        {"tool_calls": [{"function": {"name": "t", "arguments": "{nao e json"}}]}, detect_text_tools=False
    )
    assert calls[0]["function"]["arguments"] == {}


# --- HTTP -------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_payload_carries_effort_auth_and_converted_tools(http):
    http.respond(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}]}))
    svc = _service(api_key="sk-secret", reasoning_effort="low", max_tokens=77, temperature=0.3)

    result = await svc.chat_completion_with_tools(
        [{"role": "user", "content": "oi"}],
        [{"function_declarations": [{"name": "t", "parameters": {"type": "OBJECT"}}]}],
    )

    request = http.requests[0]
    body = json.loads(request.content)
    assert request.url.path == "/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer sk-secret"
    assert (body["reasoning_effort"], body["max_tokens"], body["temperature"]) == ("low", 77, 0.3)
    assert body["tools"][0]["function"]["parameters"]["type"] == "object"
    assert result["content"] == "pong" and result["tool_calls"] == []


@pytest.mark.asyncio
async def test_supports_tools_false_omits_tools_from_payload(http):
    http.respond(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]}))
    svc = _service(supports_tools=False)
    await svc.chat_completion_with_tools([{"role": "user", "content": "oi"}], [{"name": "t"}])
    assert "tools" not in json.loads(http.requests[0].content)


@pytest.mark.asyncio
async def test_streaming_assembles_tool_call_deltas_and_routes_reasoning(http):
    body = _sse(
        _delta(role="assistant", reasoning_content="pen"),
        _delta(reasoning_content="sando"),
        _delta(tool_calls=[{"index": 0, "id": "call_1", "type": "function", "function": {"name": "horario_tool", "arguments": ""}}]),
        _delta(tool_calls=[{"index": 0, "function": {"arguments": '{"company'}}]),
        _delta(tool_calls=[{"index": 0, "function": {"arguments": '_id": "abc"}'}}]),
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    )
    http.respond(lambda r: httpx.Response(200, text=body, headers={"content-type": "text/event-stream"}))
    thinking: List[str] = []

    result = await _service().stream_chat_completion_with_tools(
        [{"role": "user", "content": "oi"}], [{"name": "horario_tool"}],
        on_thinking_token=lambda t: thinking.append(t),
    )

    assert "".join(thinking) == "pensando"
    assert result["finish_reason"] == "tool_calls"
    assert result["tool_calls"][0]["function"] == {"name": "horario_tool", "arguments": {"company_id": "abc"}}


@pytest.mark.asyncio
async def test_typed_stream_yields_tool_call_in_agent_graph_shape(http):
    body = _sse(
        _delta(tool_calls=[{"index": 0, "id": "c", "function": {"name": "t", "arguments": '{"a": 1}'}}]),
    )
    http.respond(lambda r: httpx.Response(200, text=body))
    events = [e async for e in _service().astream_chat_completion_with_thinking(
        [{"role": "user", "content": "oi"}], tools=[{"name": "t"}])]
    assert events == [("tool_call", {"name": "t", "arguments": {"a": 1}})]


@pytest.mark.asyncio
async def test_http_errors_map_to_inference_errors(http):
    http.respond(lambda r: httpx.Response(429, text="slow down"))
    with pytest.raises(InferenceRateLimitError):
        await _service().chat_completion([{"role": "user", "content": "oi"}])

    http.respond(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(InferenceServiceError, match="HTTP 500"):
        await _service().chat_completion([{"role": "user", "content": "oi"}])


# --- criptografia ------------------------------------------------------------ #

def test_secret_roundtrip_and_ciphertext_hides_plaintext():
    token = encrypt_secret("sk-abc")
    assert "sk-abc" not in token and decrypt_secret(token) == "sk-abc"


# --- registry + fallback ----------------------------------------------------- #

def _seed_gateway(db, *, agent_type="default", model_active=True, name="gw") -> GatewayModel:
    gateway = InferenceGateway(name=name, base_url="http://gw.test/v1", api_key_encrypted=encrypt_secret("k"))
    model = GatewayModel(name="m", model_id="m1", reasoning_effort="low", is_active=model_active)
    gateway.models.append(model)
    db.add(gateway)
    db.flush()
    db.add(GatewayAssignment(agent_type=agent_type, gateway_model_id=model.id))
    db.commit()
    gateway_registry.invalidate()
    return model


def test_registry_prefers_specific_assignment_then_default(db):
    _seed_gateway(db, agent_type="default", name="gw-default")
    specific = GatewayModel(name="s", model_id="specific", gateway_id=db.query(InferenceGateway).one().id)
    db.add(specific)
    db.flush()
    db.add(GatewayAssignment(agent_type="whatsapp_agent", gateway_model_id=specific.id))
    db.commit()
    gateway_registry.invalidate()

    assert gateway_registry.get_assigned_service("whatsapp_agent").model == "specific"
    assert gateway_registry.get_assigned_service("default").model == "m1"


def test_registry_inactive_model_means_no_gateway(db):
    _seed_gateway(db, model_active=False)
    assert gateway_registry.get_assigned_service("default") is None


def test_ensure_default_gateway_is_idempotent_and_preserves_user_edits(db):
    first = gateway_registry.ensure_default_gateway(db)
    assert first is not None and first.models[0].reasoning_effort == "low"
    first.models[0].reasoning_effort = "high"
    db.commit()

    assert gateway_registry.ensure_default_gateway(db) is None
    assert db.query(GatewayModel).one().reasoning_effort == "high"


@pytest.mark.asyncio
async def test_fallback_service_uses_gateway_when_assigned(db, http):
    _seed_gateway(db)
    http.respond(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "via gateway"}}]}))

    service = FallbackInferenceService("whatsapp_agent")
    result = await service.chat_completion([{"role": "user", "content": "oi"}])

    assert result["content"] == "via gateway"
    assert service.uses_gateway and service.model == "m1"


@pytest.mark.asyncio
async def test_fallback_goes_to_default_provider_when_gateway_fails_before_first_token(db, http, monkeypatch):
    _seed_gateway(db)
    http.respond(lambda r: httpx.Response(500, text="down"))
    service = FallbackInferenceService("whatsapp_agent")

    async def default_stream(**kwargs):
        yield ("response", "do provedor padrao")

    monkeypatch.setattr(service.primary_service, "astream_chat_completion_with_thinking", default_stream)
    events = [e async for e in service.astream_chat_completion_with_thinking([{"role": "user", "content": "oi"}])]

    assert events == [("response", "do provedor padrao")]


@pytest.mark.asyncio
async def test_fallback_does_not_restart_elsewhere_after_partial_gateway_output(db, http, monkeypatch):
    _seed_gateway(db)

    def cut_stream(request):
        # Um token chega e a conexao e encerrada com erro no meio do stream.
        return httpx.Response(200, content=_PartialThenError())

    http.respond(cut_stream)
    service = FallbackInferenceService("whatsapp_agent")
    called = []

    async def default_stream(**kwargs):
        called.append(True)
        yield ("response", "duplicado")

    monkeypatch.setattr(service.primary_service, "astream_chat_completion_with_thinking", default_stream)
    got = []
    with pytest.raises(InferenceServiceError):
        async for event in service.astream_chat_completion_with_thinking([{"role": "user", "content": "oi"}]):
            got.append(event)

    assert got == [("response", "parcial")] and not called


class _PartialThenError(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield f"data: {json.dumps(_delta(content='parcial'))}\n\n".encode()
        raise httpx.ReadError("conexao caiu")

    async def aclose(self):
        return None
