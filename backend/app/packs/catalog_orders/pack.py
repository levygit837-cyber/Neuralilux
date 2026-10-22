"""Pack "catálogo & pedidos": o Business Type `restaurant` (ADR 0004)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.contracts import Tool, ToolContext
from app.packs.catalog_orders.catalog import buscar_cardapio_tool
from app.models import Conversation
from app.packs.catalog_orders import recap, session_orders
from app.packs.catalog_orders.orders import gerenciar_pedido_tool, status_pedido_tool

PROMPT_SECTION = """\
## Catálogo e pedidos

Fluxo do pedido, nesta ordem:
1. Busque com `buscar_cardapio` ANTES de citar qualquer item ou preço. Nunca invente preço nem item.
2. Adicione com `gerenciar_pedido` (acao `adicionar_item`), usando o `id` devolvido pela busca.
   Item indisponível ou fora do cardápio é recusado; ofereça outro.
3. Enquanto o pedido está em montagem, pergunte se o cliente quer mais algo. Use `remover_item` para tirar itens.
   Chame `adicionar_item` uma vez por item: não repita a chamada.
4. Colete os dados com `definir_dados`: nome, `tipo_entrega` (entrega ou retirada), endereço (só na entrega,
   com rua, número e bairro) e `forma_pagamento` (pix, dinheiro ou cartão). Para dinheiro, pergunte se precisa
   de troco (`troco_para`). Uma pergunta por vez; não aceite como nome palavras como "retirada" ou "pix".
5. Com itens e dados completos, chame `recapitular` e mostre ao cliente itens, taxa de entrega, total e dados
   (nome, entrega ou retirada, endereço, pagamento). Peça a confirmação e PARE: a resposta daquele turno é a
   recapitulação. Só chame `finalizar` quando o cliente confirmar numa mensagem seguinte. "Pode fechar" na mesma
   mensagem em que ele deu os dados NÃO é confirmação: recapitule primeiro. Qualquer mudança depois da recapitulação
   (item, endereço, pagamento, troco) exige `recapitular` e confirmação de novo.
   Se a forma de pagamento for Pix, envie o código "copia e cola" devolvido, exatamente como veio.

Regras:
- Se `finalizar` for recusado por a empresa estar fechada, diga ao cliente quando ela abre; o pedido continua salvo.
- Depois do `finalizar` o pedido está fechado e não aceita mais itens: não pergunte "quer mais algo?" nem ofereça
  acrescentar. Se ele quiser outra coisa, é um pedido novo; só ofereça isso se ele pedir.
- O total sempre vem de `gerenciar_pedido`; a taxa de entrega depende do bairro e há um pedido mínimo
  (veja em `info_empresa`). Se o pedido não bater o mínimo, diga quanto falta.
- Cancelar ou alterar um pedido já confirmado ("quero cancelar", "coloca uma coca") NÃO é caso de atendente
  enquanto ele ainda está "recebido, aguardando preparo":
  - Cancelar: chame `gerenciar_pedido` com `cancelar_pedido` (e `motivo`, se o cliente disse) e confirme o cancelamento.
    Se havia Pix, a empresa cuida do estorno: diga isso, sem prometer prazo.
  - Alterar: chame `alterar_pedido`, aplique o que ele pediu (`adicionar_item`, `remover_item`, `definir_dados`),
    chame `recapitular` e peça a confirmação do novo total. A confirmação anterior não vale mais. Se o pagamento
    era Pix, o código antigo deixa de valer e o `finalizar` devolve um novo: envie o novo, nunca o antigo.
  - Se o pedido já está em preparo, saiu ou foi entregue, a ferramenta recusa. Explique que não dá mais para mexer
    por aqui, ofereça falar com um atendente e só então chame `transferir_atendente`, com o motivo.
- "Cadê meu pedido" ou "já saiu?": use `status_pedido`.
- Horário, endereço da loja, taxas e formas de pagamento: use `info_empresa`.
- Referência a algo de uma conversa anterior ("o de ontem"): use `buscar_historico`.
- Chame `transferir_atendente` quando o cliente pedir para falar com uma pessoa, fizer uma reclamação grave
  ou relatar um problema com um pedido já feito. Depois disso você não responde mais.
"""


class CatalogOrdersPack:
    name = "catalog_orders"

    def tools(self) -> list[Tool]:
        return [buscar_cardapio_tool(), gerenciar_pedido_tool(), status_pedido_tool()]

    def system_prompt_section(self, ctx: ToolContext) -> str:
        note = session_orders.prompt_note(ctx)
        return f"{PROMPT_SECTION}\n{note}" if note else PROMPT_SECTION

    def on_session_start(self, db: Session, conversation: Conversation) -> None:
        session_orders.abandon_active_orders(db, conversation.id)

    def on_reply_delivered(self, db: Session, conversation: Conversation, turn_id: str, at: datetime) -> None:
        recap.mark_delivered(db, conversation, turn_id, at)
