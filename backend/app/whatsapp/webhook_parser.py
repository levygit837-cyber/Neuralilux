"""
Leitura dos eventos de webhook da Evolution: funções puras, sem banco nem I/O.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

# Chaves de `message` que só embrulham outra mensagem.
_WRAPPERS = ("ephemeralMessage", "viewOnceMessage", "viewOnceMessageV2", "documentWithCaptionMessage")
_MEDIA = {
    "imageMessage": ("image", "[Imagem]"),
    "videoMessage": ("video", "[Vídeo]"),
    "audioMessage": ("audio", "[Áudio]"),
    "documentMessage": ("document", "[Documento]"),
    "stickerMessage": ("sticker", "[Sticker]"),
}


@dataclass(frozen=True)
class ParsedContent:
    message_type: str
    content: str  # o que é gravado e mostrado na UI
    text: str  # texto que o Contact escreveu (corpo ou legenda); vazio em mídia sem legenda
    is_media: bool = False


def parse_content(message_data: Dict[str, Any]) -> ParsedContent:
    """Extrai tipo, conteúdo e texto de um `message` da Evolution."""
    message_data = message_data or {}
    for _ in range(len(_WRAPPERS)):
        wrapper = next((key for key in _WRAPPERS if isinstance(message_data.get(key), dict)), None)
        if wrapper is None:
            break
        message_data = message_data[wrapper].get("message") or {}

    if "conversation" in message_data:
        text = message_data["conversation"] or ""
        return ParsedContent("text", text, text)
    if "extendedTextMessage" in message_data:
        text = (message_data["extendedTextMessage"] or {}).get("text") or ""
        return ParsedContent("text", text, text)
    for key, (message_type, placeholder) in _MEDIA.items():
        if key in message_data:
            caption = (message_data[key] or {}).get("caption") or ""
            return ParsedContent(message_type, caption or placeholder, caption, is_media=True)
    return ParsedContent("unknown", "[Mensagem]", "")


def resolve_remote_jid(key: Dict[str, Any], payload: Dict[str, Any]) -> str:
    """JID do Contact. Um `@lid` é trocado pelo número real (`remoteJidAlt`/`senderPn`) quando vier."""
    remote_jid = key.get("remoteJid") or ""
    if remote_jid.endswith("@lid"):
        alternate = key.get("remoteJidAlt") or key.get("senderPn") or payload.get("senderPn")
        if alternate:
            return alternate if "@" in alternate else f"{alternate}@s.whatsapp.net"
    return remote_jid


def is_ignored_chat(remote_jid: str) -> bool:
    """Grupos e broadcast (inclui `status@broadcast`) nunca passam pelo Agent."""
    return remote_jid.endswith("@g.us") or remote_jid.endswith("@broadcast")


def unwrap_event_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    nested = data.get("data")
    if isinstance(nested, dict):
        return nested
    return data


def normalize_message_status(status: Any) -> str:
    mapping = {
        "PENDING": "pending",
        "pending": "pending",
        "SERVER_ACK": "sent",
        "sent": "sent",
        "DELIVERY_ACK": "delivered",
        "delivered": "delivered",
        "READ": "read",
        "read": "read",
    }
    return mapping.get(status, "sent")


def normalize_connection_status(state: str) -> str:
    mapping = {
        "open": "connected",
        "connected": "connected",
        "connecting": "connecting",
        "close": "disconnected",
        "closed": "disconnected",
        "disconnected": "disconnected",
    }
    return mapping.get(state, state)


def parse_message_timestamp(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        try:
            numeric = float(value)
            return datetime.fromtimestamp(numeric, tz=timezone.utc)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass

    return datetime.now(timezone.utc)
