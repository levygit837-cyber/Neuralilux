"""Pack "catálogo & pedidos": o Business Type `restaurant` (ADR 0004)."""

from __future__ import annotations

from app.agent.contracts import Tool, ToolContext
from app.packs.catalog_orders.catalog import buscar_cardapio_tool
from app.packs.catalog_orders.orders import gerenciar_pedido_tool, status_pedido_tool

PROMPT_SECTION = """\
## Catálogo e pedidos

Fluxo do pedido, nesta ordem:
1. Busque com `buscar_cardapio` ANTES de citar qualquer item ou preço. Nunca invente preço nem item.
2. Adicione com `gerenciar_pedido` (acao `adicionar_item`), usando o `id` devolvido pela busca.
   Item indisponível ou fora do cardápio é recusado; ofereça outro.
3. Pergunte se o cliente quer mais algo. Use `remover_item` para tirar itens e `ver` para recapitular.
4. Colete os dados com `definir_dados`: nome, `tipo_entrega` (entrega ou retirada), endereço (só na entrega,
   com rua, número e bairro) e `forma_pagamento` (pix, dinheiro ou cartão). Para dinheiro, pergunte se precisa
   de troco (`troco_para`). Uma pergunta por vez; não aceite como nome palavras como "retirada" ou "pix".
5. Recapitule itens, taxa de entrega e total, peça a confirmação e só então chame `finalizar`.
   Se a forma de pagamento for Pix, envie o código "copia e cola" devolvido, exatamente como veio.

Regras:
- O total sempre vem de `gerenciar_pedido`; a taxa de entrega depende do bairro e há um pedido mínimo
  (veja em `info_empresa`). Se o pedido não bater o mínimo, diga quanto falta.
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
        return PROMPT_SECTION
