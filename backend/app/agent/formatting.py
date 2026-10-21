"""Converte o markdown que o modelo escreve para a formatação do WhatsApp.

O WhatsApp entende `*negrito*`, `_itálico_` e `~tachado~`; o resto do markdown
aparece literal. A conversão só mexe em marcadores de markdown: nunca em
dígitos e pontuação, para que valores como `R$ 1.250,00` passem intactos.
"""

from __future__ import annotations

import re

_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BULLET = re.compile(r"^[ \t]*[-*][ \t]+", re.MULTILINE)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_UNDERLINE_ITALIC = re.compile(r"__(.+?)__")
_STRIKE = re.compile(r"~~(.+?)~~")
_HEADING = re.compile(r"^[ \t]*#{1,6}[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


def _heading(match: re.Match[str]) -> str:
    return f"*{match.group(1).strip('*').strip()}*"


def to_whatsapp(text: str) -> str:
    text = _LINK.sub(r"\1 (\2)", text)
    text = _BULLET.sub("• ", text)
    text = _BOLD.sub(r"*\1*", text)
    text = _UNDERLINE_ITALIC.sub(r"_\1_", text)
    text = _STRIKE.sub(r"~\1~", text)
    text = _HEADING.sub(_heading, text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return _EXTRA_BLANK_LINES.sub("\n\n", text).strip()
