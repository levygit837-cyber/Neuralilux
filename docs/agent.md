# O Agent: loop, memória e eventos

Como o Agent de uma Company executa um Turn. Termos conforme o [glossário](../CONTEXT.md); o caminho completo da Message está em [architecture.md](architecture.md). Existe um Agent por Company ([ADR 0005](adr/0005-remove-super-agent-rag-qdrant.md)).

## Um Turn

`executor.handle_incoming` (`backend/app/agent/executor.py`) é chamado uma vez por rajada de Messages de texto do Contact (ver [Agrupamento](#agrupamento-de-messages-picadas-e-digitando)):

1. Lê `Conversation.human_in_loop` do **banco**, não do objeto carregado. Em Handoff devolve `reply_text=None` e o Agent fica em silêncio.
2. Carrega a Company da Instance. Sem Company, loga erro e não responde.
3. Monta o `ToolContext` e emite `thinking_start`.
4. Monta o contexto: Summary + Recent Window da Session atual, com a Message atual sempre no fim.
5. Resolve o Gateway do tipo `whatsapp_agent` (`app/llm/registry.py`): atribuição própria, senão `default`, senão `LLMNotConfiguredError`.
6. Monta o system prompt (`prompts.py`): base genérica + seção estável de cada Pack. Só conteúdo estável por Company/Pack, idêntico byte a byte entre Turns. O que muda por Turn vai no [Turn Context](#turn-context), na última mensagem `user`.
7. Busca o Agent ativo da Company (`company_service.company_agent`) e roda `loop.run_turn` com as Tools do núcleo e do Pack do Business Type, passando `max_tokens` e `temperature` desse Agent (sem Agent: 1024 e a temperatura do Gateway).
8. Emite `thinking_end` e relê o Handoff. Se um Attendant assumiu enquanto o modelo respondia, a resposta é descartada, exceto quando foi a própria Tool de Handoff que encerrou o Turn.
9. Converte o markdown para WhatsApp (`formatting.to_whatsapp`) e devolve o `TurnResult`.

Qualquer exceção no Turn faz `rollback` e devolve a resposta fixa `FALLBACK_REPLY`; o Contact nunca fica sem retorno por uma falha interna.

## Estrutura do prompt

O system é núcleo → Pack → instruções da Company, nessa ordem (as Tools vêm antes dele no pedido ao Gateway). O núcleo e o Pack seguem a mesma estrutura: papel e objetivo → regras → fluxo → formato da resposta.

| Parte | Arquivo | O que cabe |
|---|---|---|
| Núcleo | `BASE_PROMPT` em `app/agent/prompts.py` | Papel de atendente da Company e objetivo (resolver o que o Contact veio fazer no menor número de mensagens, sem pular confirmações obrigatórias); tom gentil, caloroso e proativo; regras fixas (dados só das Tools, nunca expor falha, ID, nome de Tool ou raciocínio, Handoff quando o Contact pede ou reclama de verdade, não opinar fora do escopo nem prometer o que as Tools não confirmam); o que é o bloco do Turn; juntar as perguntas numa mensagem só; como apresentar opções (lista numerada só para poucas alternativas fechadas, até uns 8, um número por linha; texto livre sempre vale; o número responde à última lista enviada; na dúvida entre opção e quantidade, perguntar; lista longa nunca vira árvore numerada); formato curto de WhatsApp. **Nenhum termo de um ramo** (ADR 0004): `tests/agent/test_base_prompt.py` falha se aparecer pedido, cardápio, entrega ou item. |
| Pack | `PROMPT_SECTION` do Pack | O fluxo e as regras do ramo, citando as Tools pelo nome. No Pack "catálogo & pedidos": entender o pedido, adicionar, sugerir um complemento uma vez, pedir nome, entrega ou retirada (com endereço) e pagamento numa mensagem só, Recap, confirmação; quais escolhas numerar (categorias, variações do mesmo item, entrega ou retirada, forma de pagamento) e quando não numerar (pedido em texto livre completo, lista de itens longa); mais Recap antes de `finalizar`, nova Recap a cada mudança, cancelar e alterar, Pix, status, Handoff, `disponibilidade` de horário do item e aviso de empresa fechada. O que a Tool já garante não é repetido em detalhe. |
| Company | `Agent.system_prompt`, montado por `company_instructions_section` em `app/agent/prompts.py` | Instruções que a Company escreve no painel (nome do atendente, tom, avisos fixos). Entram por último, entre `<instrucoes_da_empresa>` e `</instrucoes_da_empresa>`, só quando há texto. Estável entre Turns: só muda quando a Company salva. Ver "Configuração da Company". |

Dois pontos que o texto depende do bloco do Turn: o estado aberto/fechado da Company e a Session (quando o atendimento se encerra) chegam no bloco, nunca no system, então o prompt só diz o que fazer com eles.

## Turn Context

O servidor de inferência só reaproveita o prefixo do prompt (prefix cache) se ele for idêntico desde o primeiro token, e as Tools entram no fim do system no template do LFM2.5. Por isso o system e as Tools não mudam entre Turns da mesma Company ([issue #42](https://github.com/levygit837-cyber/Neuralilux/issues/42)). O que muda vai num bloco delimitado no início da última mensagem `user` (`app/agent/turn_context.py`):

```text
<contexto_do_atendimento>
Agora é quinta-feira, 22/10/2026, 20:30 ... (clock.py)

A empresa está fechada agora e abre amanhã às 11:00 ... (clock.opening_notice; só com horários cadastrados)

<Pack.turn_context de cada Pack, ex.: nota do pedido abandonado>

Resumo da conversa até aqui (mensagens antigas):
<Summary>
</contexto_do_atendimento>

<texto do Contact>
```

- Ponto de extensão do núcleo: `turn_context.build_turn_context` (uma seção nova; o estado aberto/fechado da Company já é uma). Ponto de extensão do ramo: `Pack.turn_context(ctx)`. O texto estável de instruções continua em `system_prompt_section`.
- O bloco fica na mensagem do Turn, então é o mesmo em todos os passos do loop.
- O texto do Contact (e os `tool_result`) passa por `neutralize`: `<contexto_do_atendimento` e `</contexto_do_atendimento`, em qualquer caixa e espaçamento, viram `‹...`. O Contact não consegue abrir nem fechar o bloco.
- `ToolRegistry.schemas()` devolve as Tools na ordem dos Packs, com as chaves de cada schema em ordem alfabética.
- A Recent Window desliza em blocos (ver [Memória](#memória)), então entre dois cortes o histórico só cresce no fim e o cache cobre system + Tools + o histórico do Turn anterior. No Turn que corta, o histórico muda desde o início e o cache cobre só system + Tools.

## O loop

`loop.run_turn` ([ADR 0001](adr/0001-own-agent-loop-no-langchain.md)) é um laço curto sobre `POST /v1/messages`:

```text
repete:
  resposta = modelo(system, mensagens, schemas das Tools)
  se stop_reason != tool_use: devolve o texto
  para cada tool_use, em ordem:
      executa a Tool (registry valida o input com JSON Schema)
      se a Tool tem ends_turn: devolve o content dela e para
  anexa a resposta do assistant e os tool_result
  se passos >= max_steps (6): faz uma última chamada pedindo a resposta
```

Pontos que importam:

- **`ends_turn`**: a Tool para o loop sem nova chamada ao modelo. O `content` do `ToolResult` vira a resposta ao Contact. É assim que `transferir_atendente` encerra o Turn.
- **`max_tokens` e `temperature`**: `run_turn(..., max_tokens=DEFAULT_MAX_TOKENS, temperature=None)` repassa os dois a cada chamada ao modelo, inclusive à final de `max_steps`. O executor lê os valores do Agent da Company, editáveis em `PUT /companies/{id}/agent`; `temperature=None` deixa o Gateway decidir.
- **`max_steps`** (padrão 6): ao atingi-lo, o loop faz uma chamada final com uma instrução para responder sem Tools. Essa chamada ainda leva os schemas (o histórico tem `tool_use`/`tool_result`), mas qualquer `tool_use` nela é ignorado. Sem texto, sai `MAX_STEPS_FALLBACK_REPLY`.
- **Erros de Tool**: `ToolRegistry.execute` (`tools.py`) nunca propaga exceção. Tool desconhecida, input inválido e falha de handler viram `tool_result` com `is_error`, e o erro real vai para o log. O handler que falha dispara `rollback` da Session.
- **Nomes únicos**: duas Tools com o mesmo nome entre Packs levantam `ValueError` na montagem do registry.

## Tools

O Agent tem 6 Tools: 3 do núcleo (valem para qualquer Business Type) e 3 do Pack "catálogo & pedidos".

| Tool | Origem | O que faz |
|---|---|---|
| `info_empresa` | núcleo | Nome, endereço, telefone, horários, `aberto_agora`, formas de pagamento, chave Pix, pedido mínimo e taxas por Delivery Zone. |
| `transferir_atendente` | núcleo | Abre um Ticket, liga o Handoff e encerra o Turn (`ends_turn`) com a `frase_empatica` do Agent mais a janela de atendimento da Company. Detalhes em [operations.md](operations.md#handoff-e-tickets). |
| `buscar_historico` | núcleo | History Search nas Messages antigas do Contact. |
| `buscar_cardapio` | Pack `catalog_orders` | Busca Catalog Items disponíveis pelo que o Contact escreveu. Palavras vazias ("de", "com", "um") não contam; basta uma palavra casar no nome, na descrição curta ou na categoria, e quem casa mais palavras vem primeiro (empate: nome, depois categoria). Nomes genéricos como "refrigerante" ou "massa" encontram a categoria (sinônimos em `CATEGORY_SYNONYMS`, no Pack). Até 15 resultados com id, nome, preço e descrição. Sem consulta nem categoria devolve só as categorias com a contagem de itens. |
| `gerenciar_pedido` | Pack `catalog_orders` | Monta e fecha o Order. Ações: `adicionar_item`, `remover_item`, `ver`, `definir_dados`, `recapitular`, `finalizar`, `retomar_pedido`, `cancelar_pedido`, `alterar_pedido`. `finalizar` só fecha se o Contact recebeu a Recap (a resposta foi enviada), confirmou numa Message posterior, o Order não mudou depois dela e a Company está aberta. `cancelar_pedido` e `alterar_pedido` só valem com o Order `closed` da Session atual ou da anterior; depois do preparo (ou se for mais antigo) o erro manda oferecer Handoff. Alterar reabre o Order e exige nova Recap ([operations.md](operations.md#cancelamento-alteração-e-estorno-de-pix)). |
| `status_pedido` | Pack `catalog_orders` | Estado do Order mais recente do Contact. |

Todo acesso das Tools é escopado pelo `ToolContext`: Catalog Items e Delivery Zones pelo `company_id`, o Order pela `conversation_id`, o histórico pelo `contact_id`. Para criar Tools de outro ramo, veja [packs.md](packs.md).

## Fluxo do pedido

Resumo do que o Pack "catálogo & pedidos" garante. As regras estão no código das Tools; o prompt só orienta o modelo, então um erro de redação do modelo não fecha um pedido por engano.

| `Order.status` | O Contact ouve | O Contact pode |
|---|---|---|
| `open`, `collecting_data`, `ready_for_confirmation` | em montagem | adicionar, remover, informar dados, confirmar |
| `ready_for_confirmation` com `closed_at` | em alteração, aguardando nova confirmação | reconfirmar (ou o Order volta ao confirmado quando a Session acaba) |
| `closed` | recebido, aguardando preparo | cancelar e alterar, sem Handoff |
| `in_production`, `sent`, `delivered` | em preparo, saiu para entrega, entregue | só por Handoff |
| `cancelled` | cancelado | pedido novo |
| `abandoned` | abandonado, não foi finalizado | `retomar_pedido`, se pedir |

- **Fechar exige confirmação.** `finalizar` só fecha se o pedido está completo e acima do mínimo, a Company está aberta, o Contact viu a Recap (a resposta que a trouxe foi enviada), nada mudou desde ela e a Message que dispara o Turn é posterior à entrega. "Pode fechar" na mesma Message dos dados não conta: o Agent recapitula e espera.
- **Fora do horário não fecha.** Com `business_hours` cadastrado e a Company fechada, `finalizar` recusa com a próxima abertura ("Abre hoje às 18:00"); o Order continua salvo. Sem horários cadastrados, nada bloqueia. O mesmo vale ao pedir Handoff: a resposta traz a próxima janela de atendimento.
- **O Agent sabe se a Company está aberta desde a primeira resposta.** O bloco do Turn traz "aberta agora" ou "fechada, abre <quando>" (`clock.opening_notice`, com `is_open_at` e `next_opening`, os mesmos de `finalizar`), mais se a abertura cai antes ou depois do fim da Session (`session_timeout_minutes`). Sem `business_hours`, o bloco não diz nada sobre horário. O estado fica no bloco, nunca no `system`, que continua idêntico entre Turns. Como o Agent usa a informação (avisar, oferecer deixar o pedido montado, só prometer "fica salvo" se abre antes de a Session acabar) está no prompt do Pack.
- **Session nova abandona.** Order em montagem que atravessa o limite de inatividade vira `abandoned`; o Agent é avisado no prompt e só recria o pedido (`retomar_pedido`, com os preços de hoje) se o Contact aceitar.
- **Cancelar e alterar.** `cancelar_pedido` e `alterar_pedido` valem só para o Order `closed` confirmado na Session atual ou na anterior; depois, ou com o Order em preparo, o erro manda oferecer Handoff. Alterar reabre a montagem, invalida o Pix e exige nova Recap. A troca de status é condicional: se a Company mexe no Order no meio do caminho, nada é gravado; se ele foi para preparo, o Agent oferece Handoff, senão relê o Order e tenta de novo.
- **"Cadê meu pedido".** `status_pedido` lê o mesmo `Order.status` que a Company move no painel `/pedidos` ([operations.md](operations.md#painel-de-pedidos-status-pela-company)); a cada mudança o Contact também recebe um aviso no WhatsApp.
- **Pix.** O fechamento com Pix devolve o código "copia e cola" e o `txid`; alterar ou cancelar invalida o código antigo e o `finalizar` seguinte gera outro. Nada detecta pagamento: o estorno é manual ([operations.md](operations.md#cancelamento-alteração-e-estorno-de-pix)).
- **Handoff.** O Agent transfere quando o Contact pede uma pessoa, reclama de verdade ou relata problema num pedido já feito, com uma `frase_empatica`. Em Handoff ele fica em silêncio até o Attendant devolver ou o timeout da Company vencer ([operations.md](operations.md#como-o-handoff-termina)).

## Memória

Três camadas ([ADR 0003](adr/0003-memory-window-summary-fts.md)); a Recent Window é por Session, as outras duas por Conversation. Os limites vêm de `app/core/config.py` e podem ser trocados por variável de ambiente.

| Camada | Parâmetro | Padrão | Como funciona |
|---|---|---|---|
| Recent Window | `MEMORY_WINDOW`, `MEMORY_WINDOW_BLOCK` | 20, 10 | As Messages de texto **da Session atual** que o Summary ainda não cobre, em ordem cronológica, até 20. Passou de 20, o corte tira as mais antigas de uma vez, em blocos de 10 (`MEMORY_WINDOW_BLOCK`, de 1 a `MEMORY_WINDOW`). Messages seguidas do mesmo papel viram uma só e a primeira é sempre `user`. |
| Summary | `SUMMARY_EVERY` | 20 | Cobre exatamente o que saiu da janela: o modelo une o Summary anterior às Messages cortadas (até 1200 caracteres, lotes de no máximo 100). Messages de Sessions anteriores, que ficam fora da janela pela fronteira da Session, só viram Summary quando somam 20. |
| History Search | `HISTORY_SEARCH_LIMIT` | 8 | Tool `buscar_historico`: full-text search do Postgres (`portuguese`) nas Messages do Contact dentro da Instance. |

- O Summary é atualizado **depois** que a resposta já foi enviada (`executor.refresh_summary`, tarefa de fundo do worker com Session própria). Falha só vai para o log; o próximo Turn tenta de novo.
- **Deslizamento em blocos.** A janela é "tudo da Session atual depois de `covered_until_message_id` do Summary". Quem a encurta é o refresh do Summary, não uma contagem a cada Turn: quando a janela passa de 20 Messages, ele corta as 10 mais antigas e resume essas 10. Como as Messages chegam em pares (Contact e Agent), na prática o corte acontece com 21 ou 22 e a janela volta a 11 ou 12. Dali em diante só cresce no fim, cerca de 5 Turns até passar de 20 e cortar de novo. Se o bloco pararia numa Message do Agent, o corte avança até a janela começar em `user`. Em Turns sem corte o histórico do Turn N é prefixo exato do histórico do Turn N+1, que é o que o prefix cache do modelo aproveita.
- **Por que 10.** O cache só se perde no Turn do corte, então bloco maior o perde menos vezes, mas deixa menos conversa literal logo depois dele (a janela cai para cerca de `20 - bloco` Messages). Com 10 a janela oscila entre umas 11 e 22: o corte vem a cada ~5 Turns e o Agent nunca fica com menos de ~5 trocas literais, o suficiente para um pedido em andamento. Valor 1 volta ao deslizamento de uma Message por Turn.
- **Sem lacuna.** Cortar e resumir são a mesma gravação (`covered_until_message_id` é o início da janela), então nenhuma Message fica fora da janela e do Summary ao mesmo tempo. O refresh roda depois da resposta; até ele gravar (ou se o Gateway falhar), a janela fica acima de 20, com todas as Messages ainda nela. Isso só aumenta o histórico por um tempo e o próximo Turn tenta o corte de novo.
- A History Search nunca devolve Messages de outro Contact. No SQLite dos testes ela cai para `ILIKE`; só o Postgres usa `ts_rank` e o índice GIN da migração `0004`.
- Não há embeddings nem vetores.

### Session

Uma Conversation se divide em Sessions por inatividade ([ADR 0007](adr/0007-session-de-atendimento.md)).

- **Quando abre**: o consumer chama `sessions.roll_session` antes de gravar a Message do Contact. Se passou mais que `Company.session_timeout_minutes` (padrão 180, exatamente o limite ainda é a mesma Session) desde a última Message da Conversation, `Conversation.session_started_at` recebe o horário da Message nova. Mensagens `fromMe` nunca abrem Session.
- **O que muda**: a Recent Window só tem Messages com `timestamp >= session_started_at`. Messages anteriores contam como "fora da janela" para o Summary e continuam na History Search. `session_started_at` nulo (Conversation sem Session registrada) usa a Conversation inteira.
- **Packs**: ao abrir a Session nova, cada Pack que definir o gancho opcional `on_session_start(db, conversation)` o recebe, na mesma transação da Message. No Pack de pedidos, o Order ativo vira `abandoned`.
- **Entrega da resposta**: depois de enviar a resposta, o consumer chama `executor.reply_delivered`, que avisa os Packs com o gancho opcional `on_reply_delivered(db, conversation, turn_id, at)`. Turn que falha, fica sem resposta, tem a resposta descartada (Handoff) ou cujo envio falha não chama o gancho. No Pack de pedidos é isso que torna a Recap válida (`recap_delivered_at`); `finalizar` ainda exige que a Message do Contact seja posterior à entrega.
- **Configurar**: `PUT /api/v1/companies/{id}` com `session_timeout_minutes` (1 a 10080 minutos), ou pelo painel (Configurações > Geral).

## Configuração da Company

O painel (Configurações > Geral) lê e grava a Company no backend; nada fica em `localStorage`. As Tools leem a mesma linha, então o que o painel salva vale no próximo Turn.

- **Acesso**: `GET`/`PUT /api/v1/companies/{id}` e `/companies/{id}/agent` só aceitam o usuário da própria Company ou um superusuário; outro usuário recebe 403. `POST /companies/` e `DELETE /companies/{id}` são só do superusuário (403 para os demais, inclusive o dono), assim como alterar `business_type_id` e `is_active`. A listagem devolve só a Company do usuário (vazia sem Company); o superusuário vê todas.
- **Campos**: endereço (`address_*`), `phone` (dígitos, espaços e `+()-`, 8 a 20 dígitos), `email`, `pix_key`, `minimum_order` (0 a 100000, 2 casas, nunca `NaN`/infinito), `business_hours`, `timezone`, `session_timeout_minutes` e `handoff_timeout_hours` (1 a 720). Número tem de ser número: `true`/`false` viram 422. Texto vazio limpa o campo; campo ausente no `PUT` não muda.
- **Horários**: `{"mon": [["11:00", "14:00"], ["18:00", "02:00"]], ...}`, `HH:MM` (00:00 a 23:59, o mesmo parser que `is_open_at` usa na leitura) no fuso da Company. Fim menor ou igual ao início cruza a meia-noite (`"00:00"` é o fim do dia). Dia ausente ou lista vazia é fechado. Janelas que se sobrepõem são recusadas (422).
- **Pix**: aceita e-mail, CPF, CNPJ, celular (`+55...`) ou chave aleatória (UUID), até 77 caracteres (limite do campo EMV). Sem chave, `info_empresa` não lista `pix` e o fechamento recusa Pix.
- **Agent**: `PUT /companies/{id}/agent` com `temperature` (0 a 1; `null` usa a do Gateway), `max_tokens` (100 a 4000) e `system_prompt` (instruções da Company). O executor passa temperatura e tokens ao modelo em cada chamada do Turn.
- **Instruções da Company** (`system_prompt`, painel Configurações > Agent): até 2000 caracteres (cerca de 500 tokens: cabe nome, tom e alguns avisos fixos sem inflar o system de toda Company); acima disso o `PUT` responde 422. Texto vazio ou só espaços limpa o campo (`null`) e o trecho some do system; campo ausente no `PUT` não muda. A coluna aceita `NULL`; a migração `0013` limpa os valores legados `Atendente de <Company>` (que o seed gravava só para satisfazer o `NOT NULL`) e o seed não grava mais nada. O mesmo controle de acesso do resto do Agent (usuário da Company ou superusuário, 403 para os demais).
  - **Onde entra**: no system, depois do núcleo e do Pack, dentro de `<instrucoes_da_empresa>...</instrucoes_da_empresa>`. Não vai no bloco do Turn, então dois Turns sem salvar nada têm o mesmo system byte a byte (prefix cache). Salvar muda o system a partir do Turn seguinte.
  - **Neutralização**: o texto passa por `turn_context.neutralize` e pela mesma troca para o delimitador do trecho: `<instrucoes_da_empresa` e `</instrucoes_da_empresa` (qualquer caixa e espaçamento) e `<contexto_do_atendimento` viram `‹...`. A Company não fecha o trecho nem forja o bloco do Turn.
  - **O que não sobrescreve**: o núcleo diz que, em conflito, valem as regras do sistema. As instruções não liberam pular a Recap antes de `finalizar`, afirmar dado que as Tools não deram, expor falha interna ou deixar de fazer Handoff; servem para nome, tom e avisos fixos.

## Agrupamento de Messages picadas e "digitando"

O Contact costuma mandar a frase em pedaços ("oi", "quero", "uma calabresa"). Responder a cada pedaço geraria três respostas. O consumer grava cada Message na hora e entrega ao `TurnBatcher` (`app/whatsapp/turn_batcher.py`) uma `Entry` (id da Message gravada, texto, instante), por Conversation:

- **Janela.** `DEBOUNCE_SECONDS` (padrão 3). A primeira Message da rajada espera a Conversation ficar essa pausa sem Message nova; então roda **um** Turn com o `Group` das Messages, os textos juntos, um por linha. Mídia sem legenda não entra no grupo: recebe a resposta fixa na hora.
- **Sem duplicar nem reordenar.** O Turn tira da Recent Window exatamente os ids do `Group` (`build_context(exclude_ids=...)`) e os põe de volta, juntos e na ordem de chegada, como o fim do histórico. Mídia respondida ou Session nova no meio da rajada não mudam isso.
- **Message gravada a caminho.** Logo depois do commit o consumer pega um `Hold` do batcher; ele é solto no `submit` (ou quando a Message não vai ao Agent). A líder não fecha o grupo com `Hold` aberto, então uma Message já gravada entra no grupo em curso ou no Turn seguinte, nunca nos dois.
- **Message durante um Turn.** Fica na fila e é tratada no Turn seguinte, depois de outra pausa. Nunca há dois Turns da mesma Conversation ao mesmo tempo, e nenhuma Message é descartada. O Turn seguinte vê a resposta anterior na Recent Window.
- **`DEBOUNCE_SECONDS=0`.** Sem agrupamento: um Turn por Message, em ordem de chegada. Uma Message que chega durante um Turn espera na fila e tem o seu próprio Turn, sem juntar com outras; as Messages já gravadas e ainda na fila não entram no histórico do Turn em curso (`Group.deferred_ids`).
- **Handoff.** O gate do executor lê `human_in_loop` do banco no início de cada Turn: Attendant que assume durante a janela, ou transferência pedida na primeira Message da rajada, impedem os Turns seguintes.
- **Conversations diferentes** têm filas independentes e rodam em paralelo.
- **Confirmação no broker.** Só a Message que abre a rajada segura a entrega do RabbitMQ até o fim dos Turns; as demais voltam logo depois de gravadas. Dimensionamento do `RABBITMQ_PREFETCH` em [operations.md](operations.md#agrupamento-e-prefetch). No shutdown normal o worker espera a rajada em andamento terminar. Se ele cair no meio da janela, as Messages já gravadas ficam sem resposta até o Contact escrever de novo: as seguidoras já foram confirmadas ao broker e a redelivery da líder é descartada pelo dedup.
- **Falha no Turn.** Fica no log; as Messages que chegaram durante ele ainda geram o Turn seguinte.

Enquanto o Turn roda, o Contact vê "digitando…" no WhatsApp: `agent_turn.typing_indicator` chama `POST /chat/sendPresence/{instance}` (`presence=composing`) e renova a cada `TYPING_REFRESH_SECONDS` (padrão 20), porque a Evolution encerra a presença sozinha depois do `delay`. A chamada usa timeout de leitura de 5 s, independente do `delay`: a Evolution segura a resposta até o fim do `delay`, e estourar a leitura vale como "aceito", então `TYPING_REFRESH_SECONDS` pode passar de 30 s. A presença é cosmética: se a chamada falhar, o erro vai para o log como aviso e a resposta sai normalmente. O `send_text_message` já envia `composing` por 1,2 s antes do texto.

## Eventos em tempo real

O Turn publica eventos no event bus Redis (`app/realtime/event_bus.py`, canal `neuralilux:realtime:events`); a API os entrega pelo Socket.IO. Falha ao publicar só gera `warning`: evento de UI nunca derruba um Turn.

| Evento Socket.IO | Quando | Campos principais |
|---|---|---|
| `thinking_event` | início e fim do Turn | `conversation_id`, `event` (`thinking_start` ou `thinking_end`), `data` |
| `tool_event` | ciclo de cada Tool | `tool_name`, `phase` (`started`, `completed`, `failed`; também `waiting_input`), `input_preview`, `output_preview`, `error`, `started_at`, `finished_at`, `request_id`, `trace_id` |
| `human_handoff_requested` | a Tool `transferir_atendente` abriu o Handoff | `conversation_id`, `ticket_id`, `reason`, `contact_id`, `instance_id`, `timestamp` |
| `handoff_updated` | um Attendant assumiu ou devolveu, ou o timeout devolveu ao Agent | `conversation_id`, `ticket_id`, `change` (`assumed`, `released`, `expired`), `human_in_loop`, `assigned_to`, `timestamp` |

- Os previews são cortados em `TOOL_EVENT_PREVIEW_LIMIT` (240). Os payloads brutos (`input_payload`, `output_payload`) só saem com `TOOL_EVENT_INCLUDE_RAW_PAYLOADS=true`; deixe `false` fora de debug, pois podem conter dados do Contact.
- Os eventos vão para duas salas: `conversation:{instance}:{conversation_id}` (depois de `join_conversation`) e `instance:{instance}` (depois de `subscribe_instance`). A conexão exige o JWT em `auth.token`.
- O `conversation_id` **não é o mesmo em todos os eventos**: em `thinking_event` e `tool_event` ele é o `remote_jid` da Conversation (por exemplo `5511999999999@s.whatsapp.net`); em `human_handoff_requested` e `handoff_updated` é o UUID da Conversation. Quem assina a sala por Conversation precisa tratar os dois formatos.
- Os eventos que já existiam continuam: `new_message`, `conversation_updated`, `message_status_update`, `connection_status_update` e `qr_code_update`. A tradução de evento do bus para evento Socket.IO está em `app/realtime/socket.py` (`emit_realtime_event`).
