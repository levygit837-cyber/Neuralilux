"""Cliente httpx do protocolo Anthropic Messages para um Gateway (ADR 0002).

`POST {base_url}/v1/messages`. Sem streaming: a resposta chega inteira ou falha, entao o retry
(429, 5xx, timeout) nunca reexecuta uma resposta parcial.
"""

import re
import time
from typing import Any

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.agent.contracts import ContentBlock, MessagesRequest, MessagesResponse
from app.llm.errors import LLMError, LLMProviderError, LLMRateLimitError, LLMTimeoutError

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_ATTEMPTS = 3
_ERROR_BODY_LIMIT = 300
# Linhas antigas guardam a raiz com o sufixo `/v1` (formato do cliente OpenAI); o path `/v1/...` e do cliente.
_LEGACY_V1_SUFFIX = re.compile(r"/v1/?$")


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (LLMTimeoutError, LLMRateLimitError)):
        return True
    return isinstance(exc, LLMProviderError) and exc.status_code is not None and exc.status_code >= 500


class GatewayMessagesClient:
    """`MessagesClient` (contracts.py) sobre HTTP para um Gateway."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        gateway_name: str = "gateway",
        backoff_seconds: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._root = _LEGACY_V1_SUFFIX.sub("", base_url.rstrip("/"))
        self._api_key = api_key
        self._timeout = timeout
        self._name = gateway_name
        self._backoff = backoff_seconds
        self._transport = transport

    # --- API publica -------------------------------------------------------- #

    async def create(self, request: MessagesRequest) -> MessagesResponse:
        data = await self._request("POST", "/v1/messages", self._payload(request))
        return self._parse(data, request.model)

    async def probe(self, model: str, effort: str | None = None) -> dict[str, Any]:
        """Uma chamada minima (`max_tokens: 8`) com a configuracao salva do modelo."""
        request = MessagesRequest(
            model=model,
            system="",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
            effort=effort,
        )
        started = time.monotonic()
        response = await self.create(request)
        latency_ms = int((time.monotonic() - started) * 1000)
        text = "".join(block["text"] for block in response.content if block["type"] == "text")
        return {"content": text, "latency_ms": latency_ms}

    async def list_models(self) -> list[str]:
        """Ids que o Gateway anuncia em `GET {base_url}/v1/models`."""
        data = await self._request("GET", "/v1/models")
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise LLMProviderError(f"{self._name}: lista de modelos invalida")
        return [item["id"] for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]

    # --- mapeamento --------------------------------------------------------- #

    @staticmethod
    def _payload(request: MessagesRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
        }
        if request.system:
            payload["system"] = request.system
        if request.tools:
            payload["tools"] = request.tools
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.effort:
            payload["output_config"] = {"effort": request.effort}
        return payload

    def _parse(self, data: Any, requested_model: str) -> MessagesResponse:
        if not isinstance(data, dict) or not isinstance(data.get("content"), list):
            raise LLMProviderError(f"{self._name}: resposta sem `content`")
        blocks: list[ContentBlock] = []
        for block in data["content"]:
            kind = block.get("type") if isinstance(block, dict) else None
            if kind == "text":
                blocks.append({"type": "text", "text": block.get("text", "")})
            elif kind == "tool_use":
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": block["id"],
                        "name": block["name"],
                        "input": block.get("input") or {},
                    }
                )
            # `thinking` e demais tipos nao fazem parte do contrato do loop.
        usage = data.get("usage") or {}
        return MessagesResponse(
            content=blocks,
            stop_reason=data.get("stop_reason") or "end_turn",
            model=data.get("model") or requested_model,
            output_tokens=int(usage.get("output_tokens") or 0),
        )

    # --- transporte --------------------------------------------------------- #

    def _headers(self) -> dict[str, str]:
        headers = {"anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def _redact(self, text: str) -> str:
        if self._api_key:
            text = text.replace(self._api_key, "***")
        return text[:_ERROR_BODY_LIMIT]

    async def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        retrying = AsyncRetrying(
            retry=retry_if_exception(_is_transient),
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=wait_exponential(multiplier=self._backoff, max=10),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                return await self._send_once(method, path, body)

    async def _send_once(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as http:
                response = await http.request(method, f"{self._root}{path}", headers=self._headers(), json=body)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"{self._name}: timeout apos {self._timeout:g}s") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self._name}: falha de transporte ({type(exc).__name__})") from exc

        if response.status_code == 429:
            raise LLMRateLimitError(f"{self._name}: HTTP 429: {self._redact(response.text)}")
        if response.status_code >= 400:
            raise LLMProviderError(
                f"{self._name}: HTTP {response.status_code}: {self._redact(response.text)}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise LLMProviderError(f"{self._name}: resposta nao e JSON") from exc


__all__ = ["GatewayMessagesClient", "LLMError"]
