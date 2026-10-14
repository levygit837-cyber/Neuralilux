"""Cliente de inferencia para gateways OpenAI-compatible (`POST {base_url}/chat/completions`).

Expoe a mesma interface que os agentes ja consomem (`FallbackInferenceService`):

- `chat_completion`, `chat_completion_with_tools`
- `stream_chat_completion_with_tools` (callbacks de thinking/response)
- `astream_chat_completion_with_thinking` (tuplas `("thinking"|"response"|"tool_call", ...)`)

Normalizacao feita aqui, para que os nos dos agentes nao precisem conhecer o gateway:

- mensagens no formato Gemini (`parts` com `functionCall`/`functionResponse`) viram mensagens OpenAI
  (`tool_calls` / `role: "tool"`), casando ids por nome de funcao;
- ferramentas no formato Gemini (`function_declarations`, tipos em MAIUSCULAS) viram `tools` OpenAI;
- `reasoning_content` / `reasoning` e blocos `<think>...</think>` no conteudo viram "thinking";
- `tool_calls` nativos (completos ou em deltas) e blocos `<tool_call>{json}</tool_call>` no texto
  (modelos sem function calling nativo) viram `{"id", "type", "function": {"name", "arguments": dict}}`.
"""
import inspect
import json
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx
import structlog

from app.services.inference_service import (
    InferenceRateLimitError,
    InferenceServiceError,
    InferenceTimeoutError,
)

logger = structlog.get_logger()

_DEFAULT_PARAMETERS: Dict[str, Any] = {"type": "object", "properties": {}}


def _new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:24]}"


# --------------------------------------------------------------------------- #
# Requisicao: mensagens e ferramentas
# --------------------------------------------------------------------------- #

def _serialize_arguments(arguments: Any) -> str:
    if isinstance(arguments, str):
        return arguments
    return json.dumps(arguments or {}, ensure_ascii=False, default=str)


def _convert_plain_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    role = msg.get("role", "user")
    if role == "model":
        role = "assistant"

    content = msg.get("content")
    if role == "tool":
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False, default=str)
        return {"role": "tool", "tool_call_id": msg.get("tool_call_id", ""), "content": content}

    out: Dict[str, Any] = {"role": role, "content": content}
    if role == "assistant" and msg.get("tool_calls"):
        out["tool_calls"] = [
            {
                "id": tc.get("id") or _new_call_id(),
                "type": "function",
                "function": {
                    "name": (tc.get("function") or {}).get("name", ""),
                    "arguments": _serialize_arguments((tc.get("function") or {}).get("arguments")),
                },
            }
            for tc in msg["tool_calls"]
        ]
    elif content is None and role != "assistant":
        out["content"] = ""
    return out


def _convert_parts_message(
    role: str, parts: List[Any], pending: Dict[str, List[str]]
) -> List[Dict[str, Any]]:
    parts = [p for p in parts if isinstance(p, dict)]
    text = "".join(p["text"] for p in parts if isinstance(p.get("text"), str) and not p.get("thought"))

    if role == "system":
        return [{"role": "system", "content": text}] if text else []

    if role in ("model", "assistant"):
        calls = []
        for part in parts:
            fc = part.get("functionCall")
            if not fc:
                continue
            name = fc.get("name", "")
            call_id = _new_call_id()
            pending.setdefault(name, []).append(call_id)
            calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": name, "arguments": _serialize_arguments(fc.get("args"))},
                }
            )
        if not text and not calls:
            return []
        message: Dict[str, Any] = {"role": "assistant", "content": text or None}
        if calls:
            message["tool_calls"] = calls
        return [message]

    out: List[Dict[str, Any]] = []
    for part in parts:
        fr = part.get("functionResponse")
        if not fr:
            continue
        ids = pending.get(fr.get("name", ""))
        out.append(
            {
                "role": "tool",
                "tool_call_id": ids.pop(0) if ids else _new_call_id(),
                "content": json.dumps(fr.get("response") or {}, ensure_ascii=False, default=str),
            }
        )
    if text:
        out.append({"role": "user", "content": text})
    return out


def to_openai_messages(
    messages: List[Dict[str, Any]], system_prompt: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Converte mensagens (OpenAI ou Gemini `parts`) para o formato OpenAI."""
    out: List[Dict[str, Any]] = []
    if system_prompt:
        out.append({"role": "system", "content": system_prompt})
    pending: Dict[str, List[str]] = {}
    for msg in messages:
        if "parts" in msg:
            out.extend(_convert_parts_message(msg.get("role", "user"), msg["parts"], pending))
        else:
            out.append(_convert_plain_message(msg))
    return out


def _lower_types(schema: Any) -> Any:
    """JSON Schema do Gemini usa tipos em MAIUSCULAS (`STRING`); OpenAI exige minusculas."""
    if isinstance(schema, dict):
        return {
            key: value.lower() if key == "type" and isinstance(value, str) else _lower_types(value)
            for key, value in schema.items()
        }
    if isinstance(schema, list):
        return [_lower_types(item) for item in schema]
    return schema


def _wrap_function(declaration: Dict[str, Any]) -> Dict[str, Any]:
    function = {
        "name": declaration["name"],
        "description": declaration.get("description", ""),
        "parameters": _lower_types(declaration.get("parameters") or _DEFAULT_PARAMETERS),
    }
    return {"type": "function", "function": function}


def to_openai_tools(tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Aceita `function_declarations` (Gemini), `{"type":"function",...}` (OpenAI) ou definicao simples."""
    out: List[Dict[str, Any]] = []
    for tool in tools or []:
        declarations = tool.get("function_declarations") or tool.get("functionDeclarations")
        if declarations:
            out.extend(_wrap_function(d) for d in declarations if d.get("name"))
        elif tool.get("type") == "function" and isinstance(tool.get("function"), dict):
            out.append(_wrap_function(tool["function"]))
        elif tool.get("name"):
            out.append(_wrap_function(tool))
    return out


# --------------------------------------------------------------------------- #
# Resposta: tags, tool calls, conteudo
# --------------------------------------------------------------------------- #

def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return ""


def _parse_arguments(raw: Any, tool_name: str) -> Dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, str):  # argumentos serializados duas vezes
                parsed = json.loads(parsed)
        except json.JSONDecodeError:
            logger.warning("Malformed tool_call arguments", tool=tool_name, length=len(raw))
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def normalize_tool_call(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    function = raw.get("function") if isinstance(raw.get("function"), dict) else {}
    name = (function.get("name") or raw.get("name") or "").strip()
    if not name:
        return None
    arguments = function.get("arguments", raw.get("arguments", raw.get("parameters")))
    return {
        "id": raw.get("id") or _new_call_id(),
        "type": "function",
        "function": {"name": name, "arguments": _parse_arguments(arguments, name)},
    }


def parse_text_tool_calls(blocks: List[str]) -> List[Dict[str, Any]]:
    """Blocos `<tool_call>{"name": ..., "arguments": {...}}</tool_call>` emitidos como texto."""
    calls: List[Dict[str, Any]] = []
    for block in blocks:
        try:
            parsed = json.loads(block.strip())
        except json.JSONDecodeError:
            logger.warning("Unparseable <tool_call> block in model text", length=len(block))
            continue
        for item in parsed if isinstance(parsed, list) else [parsed]:
            call = normalize_tool_call(item) if isinstance(item, dict) else None
            if call:
                calls.append(call)
    return calls


def _partial_len(buffer: str, tags: Any) -> int:
    """Maior sufixo de `buffer` que e prefixo de alguma tag (pode ser o inicio de uma tag partida)."""
    best = 0
    for tag in tags:
        for size in range(min(len(tag) - 1, len(buffer)), best, -1):
            if buffer.endswith(tag[:size]):
                best = size
                break
    return best


class _TagParser:
    """Separa `<think>` (thinking) e `<tool_call>` (capturado em `tool_blocks`) de um fluxo de texto.

    Tags partidas entre chunks ficam retidas ate serem resolvidas, entao nunca vazam para a resposta.
    """

    def __init__(self, detect_tool_calls: bool):
        self._opens: Dict[str, Tuple[str, str]] = {"<think>": ("</think>", "thinking")}
        if detect_tool_calls:
            self._opens["<tool_call>"] = ("</tool_call>", "tool")
        self._buf = ""
        self._mode = "response"
        self._close = ""
        self._tool_buf = ""
        self.tool_blocks: List[str] = []

    def feed(self, text: str, final: bool = False) -> List[Tuple[str, str]]:
        self._buf += text
        out: List[Tuple[str, str]] = []
        while True:
            if self._mode == "response":
                hit: Optional[Tuple[int, str]] = None
                for tag in self._opens:
                    idx = self._buf.find(tag)
                    if idx >= 0 and (hit is None or idx < hit[0]):
                        hit = (idx, tag)
                if hit:
                    idx, tag = hit
                    if idx:
                        out.append(("response", self._buf[:idx]))
                    self._buf = self._buf[idx + len(tag):]
                    self._close, self._mode = self._opens[tag]
                    continue
                hold = 0 if final else _partial_len(self._buf, self._opens)
            else:
                idx = self._buf.find(self._close)
                if idx >= 0:
                    self._emit(out, self._buf[:idx])
                    self._buf = self._buf[idx + len(self._close):]
                    if self._mode == "tool":
                        self._flush_tool()
                    self._mode = "response"
                    continue
                hold = 0 if final else _partial_len(self._buf, [self._close])
            keep = len(self._buf) - hold
            if keep > 0:
                self._emit(out, self._buf[:keep])
                self._buf = self._buf[keep:]
            break
        if final and self._mode == "tool":
            self._flush_tool()
        return out

    def _emit(self, out: List[Tuple[str, str]], text: str) -> None:
        if not text:
            return
        if self._mode == "tool":
            self._tool_buf += text
        else:
            out.append((self._mode, text))

    def _flush_tool(self) -> None:
        if self._tool_buf.strip():
            self.tool_blocks.append(self._tool_buf)
        self._tool_buf = ""


def parse_assistant_message(
    message: Dict[str, Any], *, detect_text_tools: bool
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Retorna `(thinking, content, tool_calls)` normalizados de um `choices[0].message`."""
    reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
    thinking = [reasoning] if isinstance(reasoning, str) and reasoning else []
    response: List[str] = []

    parser = _TagParser(detect_text_tools)
    for kind, text in parser.feed(_content_to_text(message.get("content")), final=True):
        (thinking if kind == "thinking" else response).append(text)

    tool_calls = [
        call
        for call in (normalize_tool_call(raw) for raw in message.get("tool_calls") or [])
        if call
    ]
    if not tool_calls and parser.tool_blocks:
        tool_calls = parse_text_tool_calls(parser.tool_blocks)
    return "".join(thinking).strip(), "".join(response).strip(), tool_calls


def _error_text(error: Any) -> str:
    if isinstance(error, dict):
        return str(error.get("message") or error)[:300]
    return str(error)[:300]


async def _fire(callback: Any, token: str) -> None:
    if callback is None:
        return
    result = callback(token)
    if inspect.isawaitable(result):
        await result


# --------------------------------------------------------------------------- #
# Servico
# --------------------------------------------------------------------------- #

class GatewayInferenceService:
    """Um modelo nomeado de um gateway OpenAI-compatible."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        timeout: float = 120.0,
        supports_tools: bool = True,
        gateway_name: str = "gateway",
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.supports_tools = supports_tools
        self.gateway_name = gateway_name

    # -- helpers ----------------------------------------------------------- #

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
        tools: Optional[List[Dict[str, Any]]],
        tool_choice: str,
        stream: bool,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(messages, system_prompt),
            "stream": stream,
        }
        effective_max = max_tokens or self.max_tokens
        if effective_max:
            payload["max_tokens"] = effective_max
        effective_temp = temperature if temperature is not None else self.temperature
        if effective_temp is not None:
            payload["temperature"] = effective_temp
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        if tools and self.supports_tools:
            openai_tools = to_openai_tools(tools)
            if openai_tools:
                payload["tools"] = openai_tools
                payload["tool_choice"] = tool_choice
        return payload

    def _http_error(self, status: int, body: str) -> InferenceServiceError:
        if status == 429:
            return InferenceRateLimitError(f"Gateway '{self.gateway_name}' rate limited (HTTP 429)")
        return InferenceServiceError(
            f"Gateway '{self.gateway_name}' returned HTTP {status}: {body[:300]}"
        )

    def _transport_error(self, exc: httpx.HTTPError) -> InferenceServiceError:
        if isinstance(exc, httpx.TimeoutException):
            return InferenceTimeoutError(
                f"Gateway '{self.gateway_name}' timed out after {self.timeout}s"
            )
        return InferenceServiceError(
            f"Gateway '{self.gateway_name}' request failed: {type(exc).__name__}: {exc}"
        )

    # -- nao streaming ----------------------------------------------------- #

    async def _complete(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        payload = self._build_payload(
            messages, system_prompt, max_tokens, temperature, tools, tool_choice, stream=False
        )
        url = f"{self.base_url}/chat/completions"
        logger.info(
            "Gateway chat completion",
            gateway=self.gateway_name,
            model=self.model,
            message_count=len(payload["messages"]),
            tool_count=len(payload.get("tools", [])),
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc

        if response.status_code != 200:
            raise self._http_error(response.status_code, response.text)
        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice.get("message") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise InferenceServiceError(
                f"Gateway '{self.gateway_name}' returned an unexpected response body"
            ) from exc

        thinking, content, tool_calls = parse_assistant_message(
            message, detect_text_tools=bool(payload.get("tools"))
        )
        finish_reason = choice.get("finish_reason")
        if tool_calls:
            finish_reason = "tool_calls"
        return {
            "content": content,
            "thinking": thinking,
            "tool_calls": tool_calls,
            "model": data.get("model", self.model),
            "usage": data.get("usage") or {},
            "finish_reason": finish_reason,
        }

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        return await self._complete(messages, system_prompt, max_tokens, temperature)

    async def chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        return await self._complete(
            messages, system_prompt, max_tokens, temperature, tools, tool_choice
        )

    # -- streaming --------------------------------------------------------- #

    async def _stream(
        self, payload: Dict[str, Any]
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """Eventos: `thinking`/`response` (str), depois `tool_calls` (list), `finish`, `usage`."""
        url = f"{self.base_url}/chat/completions"
        parser = _TagParser(bool(payload.get("tools")))
        acc: Dict[int, Dict[str, Any]] = {}
        finish_reason: Optional[str] = None
        usage: Dict[str, Any] = {}

        logger.info(
            "Gateway streaming completion",
            gateway=self.gateway_name,
            model=self.model,
            message_count=len(payload["messages"]),
            tool_count=len(payload.get("tools", [])),
        )
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST", url, headers=self._headers(), json=payload
                ) as response:
                    if response.status_code != 200:
                        body = (await response.aread()).decode("utf-8", "replace")
                        raise self._http_error(response.status_code, body)

                    async for raw_line in response.aiter_lines():
                        line = raw_line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if chunk.get("error"):
                            raise InferenceServiceError(
                                f"Gateway '{self.gateway_name}' stream error: {_error_text(chunk['error'])}"
                            )
                        if chunk.get("usage"):
                            usage = chunk["usage"]
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        delta = choice.get("delta") or {}

                        reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                        if isinstance(reasoning, str) and reasoning:
                            yield ("thinking", reasoning)

                        content = _content_to_text(delta.get("content"))
                        if content:
                            for kind, text in parser.feed(content):
                                yield (kind, text)

                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index")
                            if idx is None:
                                # Deltas sem index: um id novo abre outra chamada; sem id continua a ultima.
                                idx = len(acc) if (tc.get("id") or not acc) else max(acc)
                            entry = acc.setdefault(
                                idx, {"id": "", "function": {"name": "", "arguments": ""}}
                            )
                            if tc.get("id"):
                                entry["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                entry["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                entry["function"]["arguments"] += fn["arguments"]
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc

        for kind, text in parser.feed("", final=True):
            yield (kind, text)

        tool_calls = [
            call for call in (normalize_tool_call(acc[i]) for i in sorted(acc)) if call
        ]
        if not tool_calls and parser.tool_blocks:
            tool_calls = parse_text_tool_calls(parser.tool_blocks)
        yield ("tool_calls", tool_calls)
        yield ("finish", "tool_calls" if tool_calls else finish_reason)
        yield ("usage", usage)

    async def stream_chat_completion_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tool_choice: str = "auto",
        on_thinking_token: Any = None,
        on_response_token: Any = None,
    ) -> Dict[str, Any]:
        payload = self._build_payload(
            messages, system_prompt, max_tokens, temperature, tools, tool_choice, stream=True
        )
        thinking: List[str] = []
        content: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        finish_reason: Optional[str] = None
        usage: Dict[str, Any] = {}

        async for kind, value in self._stream(payload):
            if kind == "thinking":
                thinking.append(value)
                await _fire(on_thinking_token, value)
            elif kind == "response":
                content.append(value)
                await _fire(on_response_token, value)
            elif kind == "tool_calls":
                tool_calls = value
            elif kind == "finish":
                finish_reason = value
            elif kind == "usage":
                usage = value

        return {
            "content": "".join(content).strip(),
            "thinking": "".join(thinking).strip(),
            "tool_calls": tool_calls,
            "model": self.model,
            "usage": usage,
            "finish_reason": finish_reason,
        }

    async def astream_chat_completion_with_thinking(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Tuple[str, Any], None]:
        """Rende `("thinking", str)`, `("response", str)` e `("tool_call", {"name", "arguments"})`."""
        payload = self._build_payload(
            messages, system_prompt, max_tokens, temperature, tools, "auto", stream=True
        )
        async for kind, value in self._stream(payload):
            if kind in ("thinking", "response"):
                yield (kind, value)
            elif kind == "tool_calls":
                for call in value:
                    yield (
                        "tool_call",
                        {
                            "name": call["function"]["name"],
                            "arguments": call["function"]["arguments"],
                        },
                    )

    # -- descoberta / saude ------------------------------------------------ #

    async def list_models(self) -> List[str]:
        """Ids retornados por `GET {base_url}/models`."""
        try:
            async with httpx.AsyncClient(timeout=min(self.timeout, 15.0)) as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers())
        except httpx.HTTPError as exc:
            raise self._transport_error(exc) from exc
        if response.status_code != 200:
            raise self._http_error(response.status_code, response.text)
        try:
            items = response.json().get("data") or []
        except (ValueError, AttributeError) as exc:
            raise InferenceServiceError(
                f"Gateway '{self.gateway_name}' returned an unexpected /models body"
            ) from exc
        return sorted({item["id"] for item in items if isinstance(item, dict) and item.get("id")})

    async def health_check(self) -> bool:
        try:
            await self.list_models()
            return True
        except InferenceServiceError:
            return False

    async def probe(self, prompt: str = "Responda apenas: pong") -> Dict[str, Any]:
        """Uma chamada minima para validar URL, chave, modelo e effort. Retorna latencia e texto."""
        started = time.monotonic()
        result = await self._complete(
            [{"role": "user", "content": prompt}], None, 64, 0.0
        )
        return {
            "latency_ms": int((time.monotonic() - started) * 1000),
            "content": result["content"],
            "thinking": bool(result["thinking"]),
            "finish_reason": result["finish_reason"],
        }
