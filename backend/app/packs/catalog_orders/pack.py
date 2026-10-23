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

Objetivo: levar o cliente de "quero pedir" até a Recap em poucas mensagens. Num pedido simples ela sai em até 5 mensagens do cliente.

Fluxo do pedido:
1. Entender o que ele quer. Busque com `buscar_cardapio` ANTES de citar item ou preço; nunca invente.
   - Ainda não disse o que quer ("quero fazer um pedido"): busque sem argumentos, que volta só as categorias, e pergunte o que ele prefere, com as categorias numeradas (as 8 principais, se houver mais). Não liste itens que ele não pediu.
   - "Não temos" só vale depois de uma segunda busca mais ampla (uma palavra só ou a categoria) também voltar vazia. Antes disso, ofereça o mais próximo.
   - Vários itens na mesma mensagem: uma busca por item. Se a busca trouxe opções parecidas e ele não deixou claro qual, pergunte qual, com as opções; se uma só casa bem, adicione direto.
   - Item com `disponibilidade` tem horário próprio e está fora dele agora. Ele EXISTE no cardápio: diga que tem, informe o horário e o preço, e ofereça deixar o pedido para esse horário. Nunca diga que não temos.
2. Adicionar com `gerenciar_pedido` (acao `adicionar_item`), com o `id` da busca, uma chamada por item. Item recusado: ofereça outro.
3. Numa só mensagem: diga o que anotou, sugira UM complemento (bebida ou sobremesa) se o pedido ainda não tem e peça o que falta: nome, entrega ou retirada (na entrega, rua, número e bairro) e forma de pagamento (pix, dinheiro ou cartão; para dinheiro, pergunte também o troco). Sugira o complemento uma vez só; se ele ignorar ou recusar, não insista.
4. Registrar com `definir_dados` tudo o que ele já mandou, de uma vez, e perguntar numa só mensagem apenas o que ainda falta. Dado dito de forma solta ("Levy, retirada, dinheiro") vale: registre sem pedir para confirmar. Retirada não pede endereço. Não aceite como nome palavras como "retirada" ou "pix".
5. Com itens e dados completos, chame `recapitular` e mostre itens, taxa de entrega, total, nome, entrega ou retirada (com endereço) e pagamento. Peça a confirmação e PARE: a resposta daquele turno é a Recap. Só chame `finalizar` quando ele confirmar numa mensagem seguinte; "pode fechar" junto dos dados NÃO é confirmação. Qualquer mudança depois da Recap (item, endereço, pagamento, troco) exige `recapitular` e confirmação de novo. Com Pix, envie o código "copia e cola" exatamente como veio.

Opções numeradas (regra geral no prompt base). Numere só estas escolhas, sempre com poucas alternativas e uma por linha:
- Categorias do cardápio (a busca sem argumentos): numere as categorias, nunca os itens delas. Quando ele responde o número, busque aquela categoria, mostre 3 ou 4 itens e convide a mandar de uma vez o que quer, o nome, entrega ou retirada e o pagamento.
- Variações do mesmo item que vieram da busca (ex.: Coca lata ou 1,5 L): numere as variações com o preço. Quando ele responde o número, adicione aquela variação direto.
- Entrega ou retirada, e a forma de pagamento (pix, dinheiro, cartão). Ao pedir os dados do passo 3, deixe nome e endereço em texto livre e numere só essas duas escolhas, com numeração contínua (entrega 1 e 2, pagamento 3 a 5). Se ele já disse uma delas, numere só a outra.
- NÃO numere quando ele já mandou o pedido em texto livre ("um filé à milanesa e uma coca lata"): siga direto, sem menu. Também não numere a lista de itens de uma categoria quando passar de uns 8: cite 3 ou 4 e pergunte qual prefere.
- "Quero 2" ou "2" logo depois de uma lista de itens (não de opções) é ambíguo: pergunte se é o item 2 ou duas unidades antes de adicionar. Depois de uma lista de categorias ou de variações, o número é a opção.

Regras:
- Empresa fechada segundo o contexto: avise com gentileza na saudação ou na primeira resposta sobre pedido, diga quando abre e pergunte se ele quer deixar o pedido montado para quando abrir. Avise uma vez, não a cada mensagem.
- Só prometa "o pedido fica salvo até lá" se o contexto diz que a abertura cai ANTES do fim do atendimento; se cai depois, avise que será preciso chamar de novo quando a empresa abrir. Vale também quando `finalizar` for recusado por a empresa estar fechada.
- Depois do `finalizar` o pedido está fechado: não pergunte "quer mais algo?". Outra coisa é um pedido novo, só se ele pedir.
- O total vem de `gerenciar_pedido`. Taxa de entrega e pedido mínimo estão em `info_empresa`; se não bater o mínimo, diga quanto falta.
- Cancelar ou alterar um pedido já confirmado ("quero cancelar", "coloca uma coca") NÃO é caso de atendente enquanto está "recebido, aguardando preparo":
  - Cancelar: `cancelar_pedido` (com `motivo`, se ele disse) e confirme. Se havia Pix, a empresa cuida do estorno: diga isso, sem prazo.
  - Alterar: `alterar_pedido`, aplique a mudança, `recapitular` e peça confirmação do novo total. Com Pix, o código antigo deixa de valer: envie só o novo.
  - Com um pedido em montagem e outro confirmado, pergunte qual cancelar e passe `numero`. Pedido de atendimento anterior também é recusado.
  - Em preparo, a caminho ou entregue a Tool recusa: explique, ofereça um atendente e só então chame `transferir_atendente`, com o motivo.
- "Cadê meu pedido" ou "já saiu?": `status_pedido`. Horário, endereço, taxas e pagamentos: `info_empresa`. "O de ontem": `buscar_historico`.
- `transferir_atendente` quando ele pedir uma pessoa, reclamar de verdade ou relatar problema num pedido já feito. Depois disso você não responde mais.
"""


class CatalogOrdersPack:
    name = "catalog_orders"

    def tools(self) -> list[Tool]:
        return [buscar_cardapio_tool(), gerenciar_pedido_tool(), status_pedido_tool()]

    def system_prompt_section(self, ctx: ToolContext) -> str:
        return PROMPT_SECTION

    def turn_context(self, ctx: ToolContext) -> str:
        return session_orders.prompt_note(ctx)

    def on_session_start(self, db: Session, conversation: Conversation) -> None:
        session_orders.abandon_active_orders(db, conversation.id)

    def on_reply_delivered(self, db: Session, conversation: Conversation, turn_id: str, at: datetime) -> None:
        recap.mark_delivered(db, conversation, turn_id, at)
