# Criar um Pack

Um Pack é o conjunto de Tools e instruções de um Business Type. O núcleo (`backend/app/agent/`) não conhece nenhum ramo ([ADR 0004](adr/0004-generic-core-business-packs.md)): farmácia, loja ou academia entram como mais um Pack, sem tocar no loop, na memória nem nos prompts base. O único Pack existente é "catálogo & pedidos" (`backend/app/packs/catalog_orders/`, Business Type `restaurant`); use-o como referência. Termos conforme o [glossário](../CONTEXT.md).

## O contrato

Tudo vem de `backend/app/agent/contracts.py`:

```python
@dataclass(frozen=True)
class ToolContext:            # tudo que um handler pode tocar durante um Turn
    db: Session
    company_id: str
    instance_id: str
    conversation_id: str
    contact_id: str
    remote_jid: str
    turn_id: str              # um por Turn, genérico: distingue este Turn do seguinte
    trigger_at: datetime | None   # quando chegou a Message do Contact que disparou o Turn
    turn_state: dict[str, Any]    # rascunho do Turn, livre para os Packs; some quando o Turn acaba

@dataclass(frozen=True)
class ToolResult:
    content: str              # texto devolvido ao modelo
    is_error: bool = False
    ends_turn: bool = False   # True: o loop para sem chamar o modelo de novo (ex.: Handoff)

ToolHandler = Callable[[ToolContext, dict[str, Any]], Awaitable[ToolResult]]

@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]   # JSON Schema (Draft 2020-12)
    handler: ToolHandler

class Pack(Protocol):
    name: str
    def tools(self) -> list[Tool]: ...
    def system_prompt_section(self, ctx: ToolContext) -> str: ...  # estável por Company, vai no system
    def turn_context(self, ctx: ToolContext) -> str: ...            # muda por Turn, vai no bloco do Turn ("" se não há)

# Opcional, fora do Protocol: define-se só se o ramo tem pendência ao trocar de Session.
#     def on_session_start(self, db: Session, conversation: Conversation) -> None: ...
#     def on_reply_delivered(self, db: Session, conversation: Conversation, turn_id: str, at: datetime) -> None: ...
```

Regras que o `ToolRegistry` (`app/agent/tools.py`) impõe:

- O `input_schema` é validado antes do handler; input inválido volta ao modelo como `tool_result` com `is_error`, sem chamar o handler.
- Exceção no handler nunca sai do registry: vira erro genérico para o modelo, `rollback` da Session e log. Erro **esperado** (item inexistente, dado inválido) deve ser um `ToolResult(is_error=True)` com mensagem útil, não uma exceção.
- O nome da Tool é único entre todos os Packs do Agent, núcleo incluído (`info_empresa`, `transferir_atendente`, `buscar_historico` já existem). Duplicata levanta `ValueError` na montagem.
- `ends_turn=True` entrega o `content` ao Contact como resposta final.

## Convenções do repositório

- Nomes de Tool e de argumentos em português, em `snake_case` (`buscar_cardapio`, `gerenciar_pedido`).
- Escopo sempre pelo `ToolContext`: filtre dados da Company por `ctx.company_id`, dados do Contact por `ctx.contact_id` (e `ctx.instance_id`), estado da Conversation por `ctx.conversation_id`. Nunca confie num id que o modelo informou no input para escolher a Company.
- Devolva JSON (`json.dumps(..., ensure_ascii=False)`) com chaves legíveis; o modelo lê o texto.
- Uma Tool que grava só grava depois de validar tudo; falhou, nada muda (veja `catalog_orders/orders.py`).
- `on_session_start` é **opcional**: o núcleo só o chama se o Pack o definir (`getattr`). Roda quando uma Session nova substitui a anterior ([ADR 0007](adr/0007-session-de-atendimento.md)), na transação que grava a Message, sem `commit`. Use para tratar o que ficou pendente do ramo; o Pack de pedidos marca o Order aberto como `abandoned`. Sem pendência, não defina o método.
- `on_reply_delivered` também é **opcional**. Roda depois de a resposta do Turn `turn_id` ter sido enviada ao Contact, nunca antes, e não roda se o Turn falhou, ficou sem resposta, teve a resposta descartada ou o envio falhou. Use quando o ramo precisa saber que o Contact viu algo; o Pack de pedidos só dá a Recap por apresentada aqui.
- `turn_state` é rascunho por Turn: cada Pack guarda o que precisar sob a chave do próprio nome (`ctx.turn_state["catalog_orders"]`), sem colidir com outro Pack e sem o núcleo conhecer o conteúdo (ADR 0004). O `turn_id` e o `turn_state` são recriados a cada Turn; o que precisa sobreviver a ele vai para o banco.
- A `system_prompt_section` descreve o fluxo e as regras do ramo, citando as Tools pelo nome, na mesma estrutura do núcleo (objetivo → fluxo → regras). Ela é anexada ao prompt base; não repita o que o prompt base já diz (papel, tom, formato, regras fixas) nem o que a Tool já garante. Vocabulário do ramo (pedido, cardápio, entrega) mora aqui, nunca no núcleo. Tem de ser **estável**: o mesmo texto, byte a byte, entre Turns da mesma Company, senão o prefix cache do servidor de inferência não vale. Divisão completa em [agent.md](agent.md#estrutura-do-prompt).
- O que muda de um Turn para o outro (nota de pedido abandonado, estado do dia) vai em `turn_context(ctx)`, que o executor põe no bloco `<contexto_do_atendimento>` da última mensagem `user` ([Turn Context](agent.md#turn-context)). Devolva `""` quando não há nada. O Pack de pedidos devolve ali a nota do pedido abandonado.

## Exemplo: Pack de academia

Exemplo mínimo e completo, só como documentação (não existe no código). Uma Tool, `consultar_planos`, devolve os planos da Company. Para ficar curto, o snippet usa uma constante no lugar de uma tabela; num Pack real os planos viveriam num model próprio do Pack, filtrado por `ctx.company_id`.

```python
# backend/app/packs/gym/pack.py
from __future__ import annotations

import json
from typing import Any

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.models import Company

PLANOS = [
    {"plano": "Mensal", "modalidades": ["musculação"], "preco": 129.90},
    {"plano": "Trimestral", "modalidades": ["musculação", "aulas coletivas"], "preco": 329.90},
]

PROMPT_SECTION = """\
## Planos e matrículas

- Para falar de planos, valores ou modalidades, use `consultar_planos` ANTES de citar qualquer preço. Nunca invente.
- Matrícula, cancelamento e cobrança são com a recepção: chame `transferir_atendente`.
"""


async def _consultar_planos(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    company = ctx.db.get(Company, ctx.company_id)
    if company is None:
        return ToolResult(content=json.dumps({"erro": "Empresa não encontrada."}), is_error=True)

    modalidade = str(args.get("modalidade") or "").strip().lower()
    planos = [p for p in PLANOS if not modalidade or modalidade in p["modalidades"]]
    return ToolResult(
        content=json.dumps({"academia": company.name, "planos": planos}, ensure_ascii=False)
    )


def consultar_planos_tool() -> Tool:
    return Tool(
        name="consultar_planos",
        description=(
            "Lista os planos da academia com modalidades e preço mensal. Use sempre antes de citar um valor. "
            "Sem argumentos, lista todos os planos."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "modalidade": {"type": "string", "description": "Filtra por modalidade, ex: 'musculação'."},
            },
            "additionalProperties": False,
        },
        handler=_consultar_planos,
    )


class GymPack:
    name = "gym"

    def tools(self) -> list[Tool]:
        return [consultar_planos_tool()]

    def system_prompt_section(self, ctx: ToolContext) -> str:
        return PROMPT_SECTION

    def turn_context(self, ctx: ToolContext) -> str:
        return ""
```

### Ligar o Pack a um Business Type

1. Crie a pasta do Pack em `backend/app/packs/gym/` (com `__init__.py`) e o `pack.py` acima.
2. Registre o ramo em `backend/app/packs/registry.py`, a única mudança fora da pasta do Pack:

   ```python
   from app.packs.gym.pack import GymPack

   PACKS_BY_BUSINESS_TYPE: dict[str, Callable[[], Pack]] = {
       "restaurant": CatalogOrdersPack,
       "gym": GymPack,
   }
   ```

3. Garanta que existe um Business Type com `slug="gym"` e que a Company aponta para ele (`Company.business_type_id`). O seed (`scripts/seed_data.py`, `create_business_types`) só cria `restaurant`, `clinic`, `store` e `services`; adicione o novo `slug` lá ou insira a linha em `business_types`.

`executor.packs_for(company)` devolve `[CorePack(), pack]`: o núcleo sempre vale, e uma Company cujo Business Type não tem Pack fica só com as 3 Tools do núcleo. A seleção é por `Business Type.slug`, em `pack_for_company`.

### Testar um Pack

Siga os testes existentes em `backend/tests/packs/`:

- `tests/pack_helpers.py` monta duas Companies isoladas (`make_world`) e traz `call` e `tool_named`; use-os para provar o escopo por `company_id`.
- `tests/packs/test_packs_registry.py` mostra como afirmar o Pack de cada Business Type e que um ramo sem Pack só recebe o núcleo.
- `tests/agent_fakes.py` tem `FakeMessagesClient` para roteirizar o modelo num Turn completo sem rede.

Teste comportamento: validação de input, escopo entre Companies, erro esperado e `ends_turn`. Não teste o texto do prompt nem a ordem de campos do JSON.

## Checklist

- [ ] Nomes de Tool únicos e em português.
- [ ] `input_schema` com `additionalProperties: false` e `required` correto.
- [ ] Todo acesso filtrado por `ctx.company_id`, `ctx.contact_id` ou `ctx.conversation_id`.
- [ ] Erros esperados como `ToolResult(is_error=True)`.
- [ ] Entrada em `PACKS_BY_BUSINESS_TYPE` e Business Type com o mesmo `slug`.
- [ ] Nada do ramo dentro de `backend/app/agent/`.
- [ ] Testes em `backend/tests/packs/`.

Para integrar um sistema de gestão externo a um Pack, veja [integrations.md](integrations.md).
