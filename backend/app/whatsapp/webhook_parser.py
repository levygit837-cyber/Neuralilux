"""
Leitura dos eventos de webhook da Evolution: funções puras, sem banco nem I/O.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

# Chaves de `message` que só embrulham outra mensagem. `associatedChildMessage` é cada foto/vídeo de um álbum.
_WRAPPERS = (
    "ephemeralMessage",
    "viewOnceMessage",
    "viewOnceMessageV2",
    "documentWithCaptionMessage",
    "associatedChildMessage",
)
_MEDIA = {
    "imageMessage": ("image", "[Imagem]"),
    "videoMessage": ("video", "[Vídeo]"),
    "audioMessage": ("audio", "[Áudio]"),
    "documentMessage": ("document", "[Documento]"),
    "stickerMessage": ("sticker", "[Sticker]"),
}
# Chaves que só carregam metadados: sozinhas, a mensagem não tem conteúdo.
_CONTEXT_ONLY = ("messageContextInfo", "messageSecret")
# Tipos que o WhatsApp não mostra como balão de conversa.
_INVISIBLE = frozenset(
    {
        "protocolMessage",
        "reactionMessage",
        "albumMessage",  # só o cabeçalho do álbum; as fotos chegam como `associatedChildMessage`
        "senderKeyDistributionMessage",
        "pollUpdateMessage",
        "editedMessage",
        "keepInChatMessage",
        "pinInChatMessage",
    }
)


@dataclass(frozen=True)
class ParsedContent:
    message_type: str
    content: str  # o que é gravado e mostrado na UI
    text: str  # texto que o Contact escreveu (corpo ou legenda); vazio em mídia sem legenda
    is_media: bool = False


def webhook_message_ids(payload: Dict[str, Any]) -> list[str]:
    """Ids das Messages do payload, para logar um evento perdido.

    `messages.upsert` traz `key.id` (em `data` ou, no envelope do consumer, em `data.data`);
    `messages.update` é plano e traz só `keyId`.
    """
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("data"), dict):
        data = data["data"]
    ids = []
    for item in data if isinstance(data, list) else [data]:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        message_id = (key.get("id") if isinstance(key, dict) else None) or item.get("keyId")
        if message_id:
            ids.append(str(message_id))
    return ids


def _unwrap(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Desembrulha `ephemeralMessage`, `viewOnce*` etc. até a mensagem de verdade."""
    for _ in range(len(_WRAPPERS)):
        wrapper = next((key for key in _WRAPPERS if isinstance(message_data.get(key), dict)), None)
        if wrapper is None:
            break
        message_data = message_data[wrapper].get("message") or {}
    return message_data


def parse_content(message_data: Dict[str, Any]) -> ParsedContent:
    """Extrai tipo, conteúdo e texto de um `message` da Evolution."""
    message_data = _unwrap(message_data or {})
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


def parsed_from_stored(message_type: str | None, content: str | None) -> ParsedContent:
    """O `ParsedContent` de uma Message já gravada (a recuperação não tem o payload do webhook).

    Mídia sem legenda foi gravada com o marcador (`[Imagem]`...): ela volta sem texto, como no webhook.
    """
    content = content or ""
    if message_type == "text":
        return ParsedContent("text", content, content)
    for known_type, placeholder in _MEDIA.values():
        if message_type == known_type:
            return ParsedContent(known_type, content, "" if content == placeholder else content, is_media=True)
    return ParsedContent(message_type or "unknown", content, "")


def resolve_remote_jid(key: Dict[str, Any], payload: Dict[str, Any]) -> str:
    """JID do Contact. Um `@lid` é trocado pelo número real (`remoteJidAlt`/`senderPn`) quando vier."""
    remote_jid = key.get("remoteJid") or ""
    if remote_jid.endswith("@lid"):
        alternate = key.get("remoteJidAlt") or key.get("senderPn") or payload.get("senderPn")
        if alternate:
            return alternate if "@" in alternate else f"{alternate}@s.whatsapp.net"
    return remote_jid


def is_ignored_chat(remote_jid: str) -> bool:
    """Broadcast (inclui `status@broadcast`) nunca é gravado. Grupos são gravados, mas não passam pelo Agent."""
    return remote_jid.endswith("@broadcast")


def is_group_chat(remote_jid: str) -> bool:
    return remote_jid.endswith("@g.us")


def is_invisible_message(message_data: Dict[str, Any]) -> bool:
    """Mensagem que o WhatsApp não mostra como balão (protocolo, reação, enquete, edição, chaves de grupo)
    ou sem conteúdo nenhum: nunca vira linha de Message."""
    message_data = _unwrap(message_data or {})
    keys = {key for key in message_data if key not in _CONTEXT_ONLY}
    if not keys:
        return True
    if "conversation" in keys or "extendedTextMessage" in keys or keys & _MEDIA.keys():
        return False
    return bool(keys & _INVISIBLE)


def unwrap_event_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    nested = data.get("data")
    if isinstance(nested, dict):
        return nested
    return data


# Ordem do domínio: o status só avança. `failed` fica abaixo de `sent`: só vale enquanto a Message está
# `pending`, e qualquer ack real a tira de `failed`.
# Hoje o backend nunca grava `pending` (toda Message nasce `sent`), então `ERROR` -> `failed` não tem efeito:
# `failed` (rank 1) fica abaixo de `sent` (rank 2) e seria ignorado como status velho.
MESSAGE_STATUS_RANK = {"pending": 0, "failed": 1, "sent": 2, "delivered": 3, "read": 4}

_EVOLUTION_MESSAGE_STATUS = {
    "PENDING": "pending",
    "ERROR": "failed",
    "SERVER_ACK": "sent",
    "DELIVERY_ACK": "delivered",
    "READ": "read",
    "PLAYED": "read",  # áudio/vídeo tocado: já foi lido
}


def normalize_message_status(status: Any) -> str | None:
    """Status da Evolution (`StatusMessage`) no domínio; `None` para o que não é progresso de entrega (ex.: `DELETED`)."""
    if not isinstance(status, str):
        return None
    if status in MESSAGE_STATUS_RANK:
        return status
    return _EVOLUTION_MESSAGE_STATUS.get(status)


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
