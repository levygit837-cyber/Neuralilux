"""Cliente httpx do protocolo Anthropic Messages para um Gateway (ADR 0002).

`POST {base_url}/v1/messages`. Sem streaming: a resposta chega inteira ou falha, entao o retry
(429, 5xx, timeout) nunca reexecuta uma resposta parcial. Cada chamada tenta ate `max_attempts` vezes, mas
os retries saem do `RetryBudget` do Turn (`MessagesRequest.retry_budget`), compartilhado por todas as chamadas
dele. A espera e jitter exponencial; `Retry-After` do 429/503/529 manda no lugar dela. 4xx nunca tem retry.
"""

import asyncio
import math
import random
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
import structlog

from app.agent.contracts import ContentBlock, MessagesRequest, MessagesResponse
from app.core import http_clients
from app.llm.errors import LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.llm.retry import RetryBudget

logger = structlog.get_logger()

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_TIMEOUT_SECONDS = 60.0
MAX_ATTEMPTS = 3
MAX_BACKOFF_SECONDS = 10.0
_RETRY_AFTER_STATUSES = frozenset({429, 503, 529})
_ERROR_BODY_LIMIT = 300
# Linhas antigas guardam a raiz com o sufixo `/v1` (formato do cliente OpenAI); o path `/v1/...` e do cliente.
_LEGACY_V1_SUFFIX = re.compile(r"/v1/?$")


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (LLMTimeoutError, LLMRateLimitError)):
        return True
    return isinstance(exc, LLMProviderError) and exc.status_code is not None and exc.status_code >= 500


def _retry_after(response: httpx.Response) -> float | None:
    """Segundos pedidos em `Retry-After` (numero ou data HTTP) nos status que o respeitam; None se ausente ou ilegivel."""
    if response.status_code not in _RETRY_AFTER_STATUSES:
        return None
    raw = response.headers.get("retry-after", "").strip()
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    if not math.isfinite(seconds):
        return None
    return max(0.0, seconds)


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
        max_attempts: int = MAX_ATTEMPTS,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        uniform: Callable[[float, float], float] = random.uniform,
    ):
        self._root = _LEGACY_V1_SUFFIX.sub("", base_url.rstrip("/"))
        self._api_key = api_key
        self._timeout = timeout
        self._name = gateway_name
        self._backoff = backoff_seconds
        self._max_attempts = max_attempts
        self._transport = transport
        self._own_http: httpx.AsyncClient | None = None
        self._sleep = sleep
        self._uniform = uniform

    # --- API publica -------------------------------------------------------- #

    async def create(self, request: MessagesRequest) -> MessagesResponse:
        data = await self._request("POST", "/v1/messages", self._payload(request), request.retry_budget)
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
            raise self._malformed("lista de modelos sem `data`")
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
        """Valida o corpo; qualquer desvio do formato vira `LLMProviderError` (nunca KeyError/TypeError)."""
        if not isinstance(data, dict) or not isinstance(data.get("content"), list):
            raise self._malformed("sem `content`")
        blocks: list[ContentBlock] = []
        for block in data["content"]:
            if not isinstance(block, dict):
                raise self._malformed("bloco de `content` nao e objeto")
            kind = block.get("type")
            if kind == "text":
                text = block.get("text")
                if not isinstance(text, str):
                    raise self._malformed("bloco `text` sem `text`")
                blocks.append({"type": "text", "text": text})
            elif kind == "tool_use":
                block_id, name, tool_input = block.get("id"), block.get("name"), block.get("input", {})
                if not isinstance(block_id, str) or not block_id or not isinstance(name, str) or not name:
                    raise self._malformed("bloco `tool_use` sem `id`/`name`")
                if tool_input is None:
                    tool_input = {}
                if not isinstance(tool_input, dict):
                    raise self._malformed("`tool_use.input` nao e objeto")
                blocks.append({"type": "tool_use", "id": block_id, "name": name, "input": tool_input})
            # `thinking` e demais tipos nao fazem parte do contrato do loop.

        stop_reason = data.get("stop_reason") or "end_turn"
        if not isinstance(stop_reason, str):
            raise self._malformed("`stop_reason` nao e texto")
        model = data.get("model") or requested_model
        if not isinstance(model, str):
            raise self._malformed("`model` nao e texto")
        return MessagesResponse(
            content=blocks, stop_reason=stop_reason, model=model, output_tokens=self._output_tokens(data.get("usage"))
        )

    def _output_tokens(self, usage: Any) -> int:
        if usage is None:
            return 0
        if not isinstance(usage, dict):
            raise self._malformed("`usage` nao e objeto")
        tokens = usage.get("output_tokens")
        if tokens is None:
            return 0
        if isinstance(tokens, bool) or not isinstance(tokens, int):
            raise self._malformed("`usage.output_tokens` nao e inteiro")
        return tokens

    def _malformed(self, detail: str) -> LLMProviderError:
        return LLMProviderError(f"{self._name}: resposta malformada ({detail})")

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

    async def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None, budget: RetryBudget | None = None
    ) -> Any:
        """Uma chamada com retry. Sem `budget` (probe, listagem, Summary) a chamada tem um orcamento so dela."""
        if budget is None:
            budget = RetryBudget.for_turn()
        attempt = 1
        while True:
            try:
                return await self._send_once(method, path, body)
            except (LLMTimeoutError, LLMRateLimitError, LLMProviderError) as exc:
                if attempt >= self._max_attempts or not _is_transient(exc):
                    raise
                delay = self._retry_delay(attempt, getattr(exc, "retry_after", None))
                if not budget.reserve(delay):
                    logger.warning("Gateway retry budget exhausted", gateway=self._name, attempt=attempt, wait=delay)
                    raise
                logger.warning("Gateway call failed, retrying", gateway=self._name, attempt=attempt, wait=delay)
                await self._sleep(delay)
                attempt += 1

    def _retry_delay(self, attempt: int, retry_after: float | None) -> float:
        """`Retry-After` (mais um jitter ate `backoff_seconds`, para os clientes nao voltarem juntos) ou jitter total."""
        if retry_after is not None:
            return retry_after + self._uniform(0.0, self._backoff)
        return self._uniform(0.0, min(self._backoff * 2 ** (attempt - 1), MAX_BACKOFF_SECONDS))

    def _http(self) -> httpx.AsyncClient:
        """Cliente HTTP do destino, compartilhado pelo processo (`http_clients`). Com `transport` (testes) o cliente é
        próprio desta instância, sobre o transporte injetado."""
        if self._transport is None:
            return http_clients.get(f"gateway:{self._root}")
        if self._own_http is None:
            self._own_http = httpx.AsyncClient(transport=self._transport)
        return self._own_http

    async def _send_once(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        try:
            response = await self._http().request(
                method, f"{self._root}{path}", headers=self._headers(), json=body, timeout=self._timeout
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"{self._name}: timeout apos {self._timeout:g}s") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"{self._name}: falha de transporte ({type(exc).__name__})") from exc

        if response.status_code == 429:
            raise LLMRateLimitError(
                f"{self._name}: HTTP 429: {self._redact(response.text)}", retry_after=_retry_after(response)
            )
        if response.status_code >= 400:
            raise LLMProviderError(
                f"{self._name}: HTTP {response.status_code}: {self._redact(response.text)}",
                status_code=response.status_code,
                retry_after=_retry_after(response),
            )
        try:
            return response.json()
        except ValueError as exc:
            raise LLMProviderError(f"{self._name}: resposta nao e JSON") from exc

