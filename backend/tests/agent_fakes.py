"""Fakes compartilhados pelos testes do núcleo do Agent."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agent.contracts import MessagesRequest, MessagesResponse, Tool, ToolContext


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def tool_use(name: str, input: dict, id: str) -> dict:
    return {"type": "tool_use", "id": id, "name": name, "input": input}


def reply(*blocks: dict) -> MessagesResponse:
    stop = "tool_use" if any(block["type"] == "tool_use" for block in blocks) else "end_turn"
    return MessagesResponse(content=list(blocks), stop_reason=stop, model="fake-model", output_tokens=10)


@dataclass
class FakeMessagesClient:
    """Devolve as respostas roteirizadas em ordem e guarda cada request recebido."""

    script: list[MessagesResponse]
    requests: list[MessagesRequest] = field(default_factory=list)

    async def create(self, request: MessagesRequest) -> MessagesResponse:
        # Fotografa as mensagens: o loop continua anexando na mesma lista depois.
        self.requests.append(
            MessagesRequest(
                model=request.model,
                system=request.system,
                messages=[dict(message) for message in request.messages],
                tools=list(request.tools),
                max_tokens=request.max_tokens,
                effort=request.effort,
                temperature=request.temperature,
            )
        )
        if not self.script:
            raise AssertionError("FakeMessagesClient chamado mais vezes que o roteiro")
        return self.script.pop(0)


@dataclass
class FakePack:
    name: str
    pack_tools: list[Tool]
    section: str = ""

    def tools(self) -> list[Tool]:
        return self.pack_tools

    def system_prompt_section(self, ctx: ToolContext) -> str:
        return self.section

    def on_session_start(self, db, conversation) -> None:
        return None
