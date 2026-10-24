# O Agent: loop, memória e eventos

Como o Agent de uma Company executa um Turn. Termos conforme o [glossário](../CONTEXT.md); o caminho completo da Message está em [architecture.md](architecture.md). Existe um Agent por Company ([ADR 0005](adr/0005-remove-super-agent-rag-qdrant.md)).

## Um Turn

`executor.handle_incoming` (`backend/app/agent/executor.py`) é chamado uma vez por rajada de Messages de texto do Contact (ver [Agrupamento](#agrupamento-de-messages-picadas-e-digitando)). Ele recebe o Agent já resolvido (veja [Qual Agent roda o Turn](#qual-agent-roda-o-turn)) e não escolhe outro:

1. Lê `Conversation.human_in_loop` do **banco**, não do objeto carregado. Em Handoff devolve `reply_text=None` e o Agent fica em silêncio.
2. Carrega a Company da Instance. Sem Company, loga erro e não responde.
3. Monta o `ToolContext` e emite `thinking_start`.
4. Monta o contexto: Summary + Recent Window da Session atual, com a Message atual sempre no fim.
5. Resolve o Gateway do tipo `whatsapp_agent` (`app/llm/registry.py`): atribuição própria, senão `default`, senão `LLMNotConfiguredError`.
6. Monta o system prompt (`prompts.py`): base genérica + seção estável de cada Pack. Só conteúdo estável por Company/Pack, idêntico byte a byte entre Turns. O que muda por Turn vai no [Turn Context](#turn-context), na última mensagem `user`.
7. Usa o Agent recebido (`agent=`) e roda `loop.run_turn` com as Tools do núcleo e do Pack do Business Type, passando `max_tokens` e `temperature` desse Agent (sem Agent: 1024 e a temperatura do Gateway).
8. Emite `thinking_end` e relê o Handoff. Se um Attendant assumiu enquanto o modelo respondia, a resposta é descartada, exceto quando foi a própria Tool de Handoff que encerrou o Turn.
9. Converte o markdown para WhatsApp (`formatting.to_whatsapp`) e devolve o `TurnResult`.

Qualquer exceção no Turn faz `rollback` e devolve a resposta fixa `FALLBACK_REPLY`; o Contact nunca fica sem retorno por uma falha interna. O mesmo vale quando o Turn estoura o prazo ([Prazos](#prazos-e-retries)).

## Qual Agent roda o Turn

Uma só função decide: `agent_service.resolve_turn_agent(db, instance)` (`backend/app/services/agent_service.py`). O consumer a chama uma vez por Message, antes de entregar ao agrupamento; o `agent_id` segue por `run_agent_turn`, que carrega o Agent na Session do Turn e o passa a `handle_incoming`. Instruções da Company, `max_tokens` e `temperature` vêm todos desse mesmo Agent.

- O Agent ligado à Instance (`Instance.agent_id`), se estiver ativo **e** for da mesma Company da Instance.
- Senão, o Agent ativo mais antigo da Company (`company_service.company_agent`).
- Sem Company ou sem Agent: `None`, e o consumer loga o erro e não responde.

A resolução só lê: não altera a Instance nem faz `commit`. Criar o Agent padrão da Company e ligá-lo à Instance acontece só em caminhos explícitos: `POST /instances/{nome}` (`instance_service.upsert_instance_for_user`) e `scripts/seed_data.py`.

## Quem acessa um Agent

O acesso é decidido por `Agent.company_id`, nunca por `Agent.owner_id`: o usuário vê e vincula só Agents ativos da própria Company; o superusuário vê todos. Usuário sem Company não vê nenhum.

- `GET /api/v1/agents/` lista os Agents ativos da Company do usuário.
- `PATCH /api/v1/instances/{nome}/agent-binding` só aceita Agent ativo da Company da Instance. Vale também para o superusuário: ele ganha acesso a qualquer Instance, não a um vínculo que o Turn ignoraria. Agent de outra Company, ou Instance sem Company, responde 404 (o Agent não existe para aquela Instance; não é um erro de formato do corpo, que seria 422).
- `GET`/`PATCH .../agent-status` e a resposta de `agent-binding` mostram o Agent que o Turn usaria (`resolve_turn_agent`), sem gravar nada: `agent_id`/`agent_name` são os dele e `agent_enabled` só é `true` se `Instance.agent_enabled` está ligado **e** esse Agent existe. Uma Instance legada com `agent_enabled=true` e sem `agent_id` aparece, portanto, ligada e com o Agent da Company, que é quem de fato responde. Depois de desvincular, `agent_enabled` é `false` e `agent_id` continua mostrando o Agent da Company, o que voltaria a responder se alguém religasse.
- `PATCH .../agent-status` com `agent_enabled=true` responde 400 quando não há Agent que o Turn possa usar.

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
- **Erros de Tool**: `ToolRegistry.execute` (`tools.py`) nunca propaga exceção. Tool desconhecida, input inválido, falha de handler e prazo estourado viram `tool_result` com `is_error`, e o erro real vai para o log. O handler que falha ou estoura o prazo dispara `rollback` da Session.
- **Nomes únicos**: duas Tools com o mesmo nome entre Packs levantam `ValueError` na montagem do registry.

## Prazos e retries

Sem prazo, um Turn podia fazer até 7 chamadas ao modelo, cada uma com 3 tentativas de 60 s, e segurar a Conversation por ~20 min. Agora há quatro limites, todos em `app/core/config.py` e trocáveis por variável de ambiente:

| Limite | Variável | Padrão | O que acontece ao estourar |
|---|---|---|---|
| Turn inteiro | `TURN_TIMEOUT_SECONDS` | 90 | O loop é cancelado (a chamada ao Gateway e a Tool em voo recebem `CancelledError`), a Session do Turn faz `rollback` e o Contact recebe `FALLBACK_REPLY`. O Turn sai sem `turn_id`: nenhum Pack valida nada dele. |
| Cada Tool | `TOOL_TIMEOUT_SECONDS` | 15 | O handler é cancelado, a Session faz `rollback` e o `tool_result` volta com `is_error`, como qualquer falha de Tool. O Turn segue. |
| Retries ao Gateway | `TURN_RETRY_BUDGET` | 2 | Gasto por **Turn**, não por chamada: as chamadas do loop dividem o mesmo `RetryBudget` (`app/llm/retry.py`). Acabou, o erro da chamada sobe e o Turn falha. |
| Espera dos retries | `TURN_RETRY_WAIT_SECONDS` | 20 | Soma do que o Turn pode esperar entre tentativas. Uma espera que não cabe no que resta não é feita: o erro sobe na hora. |

- **Quem manda no prazo.** O `TURN_TIMEOUT_SECONDS` é um `asyncio.timeout` em volta do `loop.run_turn` (`executor.handle_incoming`); ele vale mesmo se o timeout HTTP (`timeout_seconds` do Gateway, 60 s) ou o orçamento de retry fossem maiores. A Tool tem o seu `asyncio.timeout` em `ToolRegistry.execute`, e `TOOL_TIMEOUT_SECONDS` não pode passar de `TURN_TIMEOUT_SECONDS` (a config recusa). O `rollback` roda antes de a Session voltar ao consumer, então ela não fica numa transação aberta.
- **Só corta em `await`.** O prazo cancela a task, e o cancelamento só chega onde o código cede o controle ao loop: I/O assíncrono, como a chamada ao Gateway, o `publish` de eventos e o `httpx` de uma Tool. Uma Tool que roda SQLAlchemy síncrono ou outro código bloqueante não é cortada no meio: o prazo vale quando ela terminar ou chegar ao próximo `await`, e nesse intervalo o worker inteiro fica parado, não só o Turn. Handler novo deve usar I/O assíncrono ou ser curto.
- **Tool cancelada pode ter efetivado.** O cancelamento interrompe o lado de cá, não o de lá: uma chamada HTTP já enviada pode ter sido processada pelo serviço externo. O `rollback` só desfaz a Session do Turn. Tool futura que escreve fora do banco (HTTP, fila) precisa ser idempotente ou conferir o efeito antes de repetir; o `tool_result` de erro manda o modelo não repetir a chamada, mas não prova que nada aconteceu.
- **O que tem retry.** Timeout, 429 e 5xx (`GatewayMessagesClient`, até `max_attempts` por chamada, 3). 4xx (400, 401, 404, 422…) nunca tem.
- **Quanto espera.** Jitter total: um sorteio entre 0 e `1 s × 2^(tentativa-1)` (teto 10 s), para os Turns não baterem juntos no Gateway. Com `Retry-After` em 429, 503 ou 529 (segundos ou data HTTP), a espera é o valor indicado (mais um jitter de até 1 s), no lugar do backoff. Se o orçamento do Turn não cobre o `Retry-After`, o cliente desiste sem esperar.
- **Fora de Turn.** Chamadas sem Turn (teste do Gateway, Summary) usam um orçamento só delas, com os mesmos valores.
- **Recap.** Turn que estoura o prazo é um Turn que falhou antes do envio: o `TurnResult` não traz `turn_id`, então `reply_delivered` nunca chama `on_reply_delivered` e a Recap que ele montou não vale ([Session](#session), glossário).
- **Debounce.** O agrupamento tem o próprio teto, `DEBOUNCE_MAX_WAIT_SECONDS` ([abaixo](#agrupamento-de-messages-picadas-e-digitando)).

## Tools

O Agent tem 7 Tools: 3 do núcleo (valem para qualquer Business Type) e 4 do Pack "catálogo & pedidos".

| Tool | Origem | O que faz |
|---|---|---|
| `info_empresa` | núcleo | Nome, endereço, telefone, horários, `aberto_agora` e `fuso_horario`. Nada de ramo: entrega, Pix, pedido mínimo e pagamento são do Pack. |
| `transferir_atendente` | núcleo | Abre um Ticket, liga o Handoff e encerra o Turn (`ends_turn`) com a `frase_empatica` do Agent mais a janela de atendimento da Company. Detalhes em [operations.md](operations.md#handoff-e-tickets). |
| `buscar_historico` | núcleo | History Search nas Messages antigas do Contact. |
| `buscar_cardapio` | Pack `catalog_orders` | Busca Catalog Items disponíveis pelo que o Contact escreveu. Palavras vazias ("de", "com", "um") não contam; basta uma palavra casar no nome, na descrição curta ou na categoria, e quem casa mais palavras vem primeiro (empate: nome, depois categoria). Nomes genéricos como "refrigerante" ou "massa" encontram a categoria (sinônimos em `CATEGORY_SYNONYMS`, no Pack). Até 15 resultados com id, nome, preço e descrição. Item com horário próprio fora da janela agora (no fuso da Company) vem com `disponibilidade`, com a próxima abertura dele ("Fora do horário agora; disponível a partir de hoje às 18:00."); ver [integrations.md](integrations.md#exemplo-sincronizar-a-disponibilidade-de-um-catalog-item). Sem consulta nem categoria devolve só as categorias com a contagem de itens. |
| `gerenciar_pedido` | Pack `catalog_orders` | Monta e fecha o Order. Ações: `adicionar_item`, `remover_item`, `ver`, `definir_dados`, `recapitular`, `finalizar`, `retomar_pedido`, `cancelar_pedido`, `alterar_pedido`. `finalizar` só fecha se o Contact recebeu a Recap (a resposta foi enviada), confirmou numa Message posterior, o Order não mudou depois dela e a Company está aberta. `cancelar_pedido` e `alterar_pedido` só valem com o Order `closed` da Session atual ou da anterior; depois do preparo (ou se for mais antigo) o erro manda oferecer Handoff. Alterar reabre o Order e exige nova Recap ([operations.md](operations.md#cancelamento-alteração-e-estorno-de-pix)). |
| `status_pedido` | Pack `catalog_orders` | Estado do Order mais recente do Contact. |
| `condicoes_pedido` | Pack `catalog_orders` | Condições para pedir, sempre da Company do contexto: `formas_pagamento` (`pix` só com chave cadastrada), `chave_pix`, `pedido_minimo` e `taxas_entrega` (zona, bairros e taxa de cada Delivery Zone ativa). Era parte de `info_empresa`; o núcleo não conhece entrega nem pagamento (ADR 0004). |

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
- **Packs**: ao abrir a Session nova, cada Pack que implementar o gancho opcional `on_session_start(db, conversation)` (Protocol `SessionStartHook`) o recebe, na mesma transação da Message. No Pack de pedidos, o Order ativo vira `abandoned`.
- **Entrega da resposta**: depois de enviar a resposta, o consumer chama `executor.reply_delivered`, que avisa os Packs que implementam o gancho opcional `on_reply_delivered(db, conversation, turn_id, at)` (Protocol `ReplyDeliveredHook`). Turn que falha, fica sem resposta, tem a resposta descartada (Handoff) ou cujo envio falha não chama o gancho. No Pack de pedidos é isso que torna a Recap válida (`recap_delivered_at`); `finalizar` ainda exige que a Message do Contact seja posterior à entrega.
- **Configurar**: `PUT /api/v1/companies/{id}` com `session_timeout_minutes` (1 a 10080 minutos), ou pelo painel (Configurações > Geral).

## Configuração da Company

O painel (Configurações > Geral) lê e grava a Company no backend; nada fica em `localStorage`. As Tools leem a mesma linha, então o que o painel salva vale no próximo Turn.

- **Acesso**: `GET`/`PUT /api/v1/companies/{id}` e `/companies/{id}/agent` só aceitam o usuário da própria Company ou um superusuário; outro usuário recebe 403. `POST /companies/` e `DELETE /companies/{id}` são só do superusuário (403 para os demais, inclusive o dono), assim como alterar `business_type_id` e `is_active`. A listagem devolve só a Company do usuário (vazia sem Company); o superusuário vê todas.
- **Campos**: endereço (`address_*`), `phone` (dígitos, espaços e `+()-`, 8 a 20 dígitos), `email`, `pix_key`, `minimum_order` (0 a 100000, 2 casas, nunca `NaN`/infinito), `business_hours`, `timezone`, `session_timeout_minutes` e `handoff_timeout_hours` (1 a 720). Número tem de ser número: `true`/`false` viram 422. Texto vazio limpa o campo; campo ausente no `PUT` não muda.
- **Horários**: `{"mon": [["11:00", "14:00"], ["18:00", "02:00"]], ...}`, `HH:MM` (00:00 a 23:59, o mesmo parser que `is_open_at` usa na leitura) no fuso da Company. Fim menor ou igual ao início cruza a meia-noite (`"00:00"` é o fim do dia). Dia ausente ou lista vazia é fechado. Janelas que se sobrepõem são recusadas (422).
- **Pix**: aceita e-mail, CPF, CNPJ, celular (`+55...`) ou chave aleatória (UUID), até 77 caracteres (limite do campo EMV). Sem chave, `condicoes_pedido` não lista `pix` e o fechamento recusa Pix.
- **Agent**: `PUT /companies/{id}/agent` com `temperature` (0 a 1; `null` usa a do Gateway), `max_tokens` (100 a 4000) e `system_prompt` (instruções da Company). O executor passa temperatura e tokens ao modelo em cada chamada do Turn.
- **Instruções da Company** (`system_prompt`, painel Configurações > Agent): até 2000 caracteres (cerca de 500 tokens: cabe nome, tom e alguns avisos fixos sem inflar o system de toda Company); acima disso o `PUT` responde 422. Texto vazio ou só espaços limpa o campo (`null`) e o trecho some do system; campo ausente no `PUT` não muda. A coluna aceita `NULL`; a migração `0013` limpa os valores legados `Atendente de <Company>` (que o seed gravava só para satisfazer o `NOT NULL`) e o seed não grava mais nada. O mesmo controle de acesso do resto do Agent (usuário da Company ou superusuário, 403 para os demais).
  - **Onde entra**: no system, depois do núcleo e do Pack, dentro de `<instrucoes_da_empresa>...</instrucoes_da_empresa>`. Não vai no bloco do Turn, então dois Turns sem salvar nada têm o mesmo system byte a byte (prefix cache). Salvar muda o system a partir do Turn seguinte.
  - **Neutralização**: o texto passa por `turn_context.neutralize` e pela mesma troca para o delimitador do trecho: `<instrucoes_da_empresa` e `</instrucoes_da_empresa` (qualquer caixa e espaçamento) e `<contexto_do_atendimento` viram `‹...`. A Company não fecha o trecho nem forja o bloco do Turn.
  - **O que não sobrescreve**: o núcleo diz que, em conflito, valem as regras do sistema. As instruções não liberam pular a Recap antes de `finalizar`, afirmar dado que as Tools não deram, expor falha interna ou deixar de fazer Handoff; servem para nome, tom e avisos fixos.

## Agrupamento de Messages picadas e "digitando"

O Contact costuma mandar a frase em pedaços ("oi", "quero", "uma calabresa"). Responder a cada pedaço geraria três respostas. O consumer grava cada Message na hora e entrega ao `TurnBatcher` (`app/whatsapp/turn_batcher.py`) uma `Entry` (id da Message gravada, texto, instante), por Conversation:

- **Janela.** `DEBOUNCE_SECONDS` (padrão 3). A primeira Message da rajada espera a Conversation ficar essa pausa sem Message nova; então roda **um** Turn com o `Group` das Messages, os textos juntos, um por linha. Mídia sem legenda não entra no grupo: recebe a resposta fixa na hora.
- **Teto da janela.** `DEBOUNCE_MAX_WAIT_SECONDS` (padrão 15, nunca menor que `DEBOUNCE_SECONDS`). Quem manda Messages a cada menos de 3 s não adia o Turn para sempre: 15 s depois da primeira Message ainda sem Turn, a líder roda com o que já chegou. O que chegar depois cai no Turn seguinte, com o teto contado de novo a partir da sua chegada. `DEBOUNCE_SECONDS=0` não usa o teto.
- **Sem duplicar nem reordenar.** O Turn tira da Recent Window exatamente os ids do `Group` (`build_context(exclude_ids=...)`) e os põe de volta, juntos e na ordem de chegada, como o fim do histórico. Mídia respondida ou Session nova no meio da rajada não mudam isso.
- **Message gravada a caminho.** Logo depois do commit o consumer pega um `Hold` do batcher; ele é solto no `submit` (ou quando a Message não vai ao Agent). A líder não fecha o grupo com `Hold` aberto, então uma Message já gravada entra no grupo em curso ou no Turn seguinte, nunca nos dois.
- **Message durante um Turn.** Fica na fila e é tratada no Turn seguinte, depois de outra pausa. Nunca há dois Turns da mesma Conversation ao mesmo tempo, e nenhuma Message é descartada. O Turn seguinte vê a resposta anterior na Recent Window.
- **`DEBOUNCE_SECONDS=0`.** Sem agrupamento: um Turn por Message, em ordem de chegada. Uma Message que chega durante um Turn espera na fila e tem o seu próprio Turn, sem juntar com outras; as Messages já gravadas e ainda na fila não entram no histórico do Turn em curso (`Group.deferred_ids`).
- **Handoff.** O gate do executor lê `human_in_loop` do banco no início de cada Turn: Attendant que assume durante a janela, ou transferência pedida na primeira Message da rajada, impedem os Turns seguintes.
- **Conversations diferentes** têm filas independentes e rodam em paralelo.
- **Confirmação no broker.** Toda Message sai do RabbitMQ (`ack`) logo depois de gravada com `turn_state = pending`; o Turn roda numa task do worker, fora do `prefetch`, então um Gateway lento não segura entregas. Se o worker cair no meio da janela ou do Turn, a Message segue `pending` no banco e a recuperação a retoma depois de `TURN_CLAIM_LEASE_SECONDS` (ou na hora, se o worker saiu por `SIGTERM`). Garantia e estados em [architecture.md](architecture.md#resposta-durável); dimensionamento do `RABBITMQ_PREFETCH` e da recuperação em [operations.md](operations.md#agrupamento-concorrência-e-prefetch).
- **Falha no Turn.** Fica no log; a Message continua `pending` (`failed`) e a recuperação tenta de novo quando a posse vence. As Messages que chegaram durante ele ainda geram o Turn seguinte.

Enquanto o Turn roda, o Contact vê "digitando…" no WhatsApp: `agent_turn.typing_indicator` chama `POST /chat/sendPresence/{instance}` (`presence=composing`) e renova a cada `TYPING_REFRESH_SECONDS` (padrão 20), porque a Evolution encerra a presença sozinha depois do `delay`. A chamada usa timeout de leitura de 5 s, independente do `delay`: a Evolution segura a resposta até o fim do `delay`, e estourar a leitura vale como "aceito", então `TYPING_REFRESH_SECONDS` pode passar de 30 s. A presença é cosmética: se a chamada falhar, o erro vai para o log como aviso e a resposta sai normalmente. O `send_text_message` já envia `composing` por 1,2 s antes do texto.

## Eventos em tempo real

O contrato é `app/realtime/events.py`: um schema Pydantic por evento, todo em snake_case, sem campo extra (`extra="forbid"`). Quem publica monta o schema e chama `publish_event` (`app/realtime/publish.py`), que coloca `{type, payload}` no event bus Redis (`app/realtime/event_bus.py`, canal `neuralilux:realtime:events`). A API revalida o payload no `emit_realtime_event` (`app/realtime/socket.py`) e só então emite: payload que não bate com o schema é descartado com `warning`. Falha ao publicar também só gera `warning`: evento de UI nunca derruba um Turn.

Todo evento leva `instance_id` e, quando fala de uma Conversation, `conversation_id`. Os dois são UUIDs. O `remote_jid` e o nome da Instance nunca viajam como identidade, então duas Instances com o mesmo nome em Companies diferentes não se cruzam.

| Evento Socket.IO | Sala | Quando | Campos (além de `instance_id`) |
|---|---|---|---|
| `new_message` | `instance:{instance_id}` | Message nova, recebida ou enviada | `conversation_id`, `message_id`, `content`, `timestamp`, `is_outgoing`, `status`, `sender_name` |
| `conversation_updated` | `instance:{instance_id}` | a Conversation mudou na lista | `conversation_id`, `contact_name`, `last_message`, `timestamp`, `unread_count`, `avatar` |
| `message_status_update` | `instance:{instance_id}` | entrega ou leitura | `conversation_id`, `message_id`, `status` |
| `connection_status_update` | `instance:{instance_id}` | a Instance conectou ou caiu | `status`, `evolution_state` |
| `qr_code_update` | `instance:{instance_id}` | a Evolution gerou um QR code | `qrcode` (texto ou objeto `{base64, code}`) |
| `handoff_updated` | `instance:{instance_id}` | um Attendant assumiu ou devolveu, ou o timeout devolveu ao Agent | `conversation_id`, `ticket_id`, `change` (`assumed`, `released`, `expired`), `human_in_loop`, `assigned_to`, `timestamp` |
| `human_handoff_requested` | `instance:{instance_id}` | a Tool `transferir_atendente` abriu o Handoff | `conversation_id`, `ticket_id`, `reason`, `timestamp` |
| `thinking_event` | `conversation:{conversation_id}` | início e fim do Turn | `conversation_id`, `event` (`thinking_start` ou `thinking_end`), `data` |
| `tool_event` | `conversation:{conversation_id}` | ciclo de cada Tool | `conversation_id`, `source`, `request_id`, `trace_id`, `tool_name`, `phase` (`waiting_input`, `started`, `completed`, `failed`), `display_name`, `input_preview`, `output_preview`, `error`, `started_at`, `finished_at` e, só com `TOOL_EVENT_INCLUDE_RAW_PAYLOADS=true`, `input_payload` e `output_payload` |

- **Uma sala por evento.** Os eventos de lista, conexão, QR e Handoff vão só para a sala da Instance; `thinking_event` e `tool_event` vão só para a sala da Conversation. Cada evento tem um formato só: `human_handoff_requested` não tem mais uma variante paralela.
- **Entrar nas salas.** `subscribe_instance` recebe `{instanceId}` e `join_conversation` recebe `{instanceId, conversationId}`, os dois UUIDs. O backend resolve a Instance pelo `id` com a regra de acesso vigente (dono, Company, superusuário) e recusa com `{ok: false}` o que o usuário não alcança. Resolver por nome ou por `evolution_instance_id` não existe mais no socket. `leave_instance`, `leave_conversation` e `send_message` seguem o mesmo formato.
- **Autenticação.** O handshake lê o cookie de sessão e confere o `Origin`. Sessão inválida recusa a conexão com `connect_error` de mensagem `unauthorized`; é o que o cliente usa para separar sessão vencida de backend fora do ar.
- **Cliente.** Um socket só, dono do `RealtimeProvider` no layout `(app)` do frontend; nenhuma tela liga ou desliga. A reconexão não tem limite de tentativas, com intervalo crescente até 10 s. `unauthorized` encerra a sessão (`endSession`); qualquer outro erro mostra o aviso "Sem conexão em tempo real" e segue tentando. A cada `connect` o cliente refaz o `subscribe_instance` e o `join_conversation` (as salas somem na queda) e, numa reconexão, invalida as queries de Instances e do dashboard e recarrega a lista, os contadores e as Messages da Conversation aberta.
- **Thinking.** O timer que apaga o Thinking depois do `thinking_end` (5 s) fica fora do store, um por Conversation. Uma rodada nova (`thinking_start`) cancela o timer da anterior.
- Os previews são cortados em `TOOL_EVENT_PREVIEW_LIMIT` (240). Os payloads brutos só saem com `TOOL_EVENT_INCLUDE_RAW_PAYLOADS=true`; deixe `false` fora de debug, pois podem conter dados do Contact.
