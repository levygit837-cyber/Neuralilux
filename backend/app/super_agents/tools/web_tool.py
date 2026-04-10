"""Web fetch/search tools for the Super Agent with SSRF protection."""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from html import unescape
from typing import Any, Dict, List
from urllib.parse import quote_plus, urlparse

import httpx
import structlog
from langchain_core.tools import tool

logger = structlog.get_logger()

ALLOWED_SCHEMES = {"http", "https"}
MAX_RESPONSE_BYTES = 1_000_000
MAX_TEXT_CHARS = 6000
REQUEST_TIMEOUT = 10.0
SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
USER_AGENT = "NeuraliluxSuperAgent/1.0 (+https://neuralilux.local)"


def _is_public_hostname(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Não foi possível resolver o host: {hostname}") from exc

    for info in infos:
        ip_value = info[4][0]
        ip_addr = ipaddress.ip_address(ip_value)
        if (
            ip_addr.is_private
            or ip_addr.is_loopback
            or ip_addr.is_link_local
            or ip_addr.is_multicast
            or ip_addr.is_reserved
            or ip_addr.is_unspecified
        ):
            return False
    return True


def _validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError("A URL deve usar http ou https")
    if not parsed.netloc:
        raise ValueError("A URL informada é inválida")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("A URL informada é inválida")
    if not _is_public_hostname(hostname):
        raise ValueError("O host informado não é permitido para fetch")
    return parsed.geturl()


def _html_to_text(html: str) -> str:
    without_scripts = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", without_scripts)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_TEXT_CHARS]


def fetch_web_content(url: str) -> Dict[str, Any]:
    safe_url = _validate_url(url)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.1"}
    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True, headers=headers) as client:
        response = client.get(safe_url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        raw_bytes = response.content[:MAX_RESPONSE_BYTES]

    text_payload = raw_bytes.decode("utf-8", errors="replace")
    if "application/json" in content_type:
        try:
            parsed_json = json.loads(text_payload)
            preview = json.dumps(parsed_json, ensure_ascii=False)[:MAX_TEXT_CHARS]
            return {
                "url": safe_url,
                "content_type": content_type,
                "title": None,
                "content": preview,
            }
        except json.JSONDecodeError:
            pass

    title_match = re.search(r"<title[^>]*>(.*?)</title>", text_payload, flags=re.IGNORECASE | re.DOTALL)
    title = unescape(title_match.group(1)).strip() if title_match else None
    text_content = _html_to_text(text_payload)
    return {
        "url": safe_url,
        "content_type": content_type,
        "title": title,
        "content": text_content,
    }


def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    search_url = f"{SEARCH_ENDPOINT}?q={quote_plus(query)}"
    payload = fetch_web_content(search_url)
    html_content = payload.get("content", "")
    if payload.get("content_type", "").startswith("text/html"):
        with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(search_url)
            response.raise_for_status()
            html = response.text
    else:
        html = html_content

    results: List[Dict[str, str]] = []
    pattern = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(html):
        href = unescape(match.group("href"))
        title_html = match.group("title")
        title = re.sub(r"<[^>]+>", " ", title_html)
        title = unescape(re.sub(r"\s+", " ", title).strip())
        if href and title:
            results.append({"title": title, "url": href})
        if len(results) >= max_results:
            break

    return {
        "query": query,
        "results": results,
        "count": len(results),
        "search_url": search_url,
    }


@tool
def web_fetch_tool(url: str) -> str:
    """Fetch content from a public URL using HTTP GET with SSRF protections."""
    try:
        payload = fetch_web_content(url)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.error("Web fetch failed", error=str(exc), url=url)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@tool
def web_search_tool(query: str, max_results: int = 5) -> str:
    """Search the public web and return a small list of results."""
    try:
        payload = search_web(query=query, max_results=max_results)
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        logger.error("Web search failed", error=str(exc), query=query)
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


__all__ = ["fetch_web_content", "search_web", "web_fetch_tool", "web_search_tool"]