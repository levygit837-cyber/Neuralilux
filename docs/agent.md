# O Agent: loop, memória e eventos

Como o Agent de uma Company executa um Turn. Termos conforme o [glossário](../CONTEXT.md); o caminho completo da Message está em [architecture.md](architecture.md). Existe um Agent por Company ([ADR 0005](adr/0005-remove-super-agent-rag-qdrant.md)).

## Um Turn

`executor.handle_incoming` (`backend/app/agent/executor.py`) é chamado pelo consumer para cada Message de texto do Contact:

1. Lê `Conversation.human_in_loop` do **banco**, não do objeto carregado. Em Handoff devolve `reply_text=None` e o Agent fica em silêncio.
2. Carrega a Company da Instance. Sem Company, loga erro e não responde.
3. Monta o `ToolContext` e emite `thinking_start`.
4. Monta o contexto: Summary + Recent Window da Session atual, com a Message atual sempre no fim.
5. Resolve o Gateway do tipo `whatsapp_agent` (`app/llm/registry.py`): atribuição própria, senão `default`, senão `LLMNotConfiguredError`.
6. Monta o system prompt (`prompts.py`): base genérica + data/hora local da Company e há quanto tempo foi a Message anterior (`clock.py`) + seção de cada Pack + Summary.
7. Busca o Agent ativo da Company (`company_service.company_agent`) e roda `loop.run_turn` com as Tools do núcleo e do Pack do Business Type, passando `max_tokens` e `temperature` desse Agent (sem Agent: 1024 e a temperatura do Gateway).
8. Emite `thinking_end` e relê o Handoff. Se um Attendant assumiu enquanto o modelo respondia, a resposta é descartada, exceto quando foi a própria Tool de Handoff que encerrou o Turn.
9. Converte o markdown para WhatsApp (`formatting.to_whatsapp`) e devolve o `TurnResult`.

Qualquer exceção no Turn faz `rollback` e devolve a resposta fixa `FALLBACK_REPLY`; o Contact nunca fica sem retorno por uma falha interna.

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
| `buscar_cardapio` | Pack `catalog_orders` | Busca Catalog Items disponíveis; até 15 resultados com id, nome, preço e descrição. |
| `gerenciar_pedido` | Pack `catalog_orders` | Monta e fecha o Order. Ações: `adicionar_item`, `remover_item`, `ver`, `definir_dados`, `recapitular`, `finalizar`, `retomar_pedido`, `cancelar_pedido`, `alterar_pedido`. `finalizar` só fecha se o Contact recebeu a Recap (a resposta foi enviada), confirmou numa Message posterior, o Order não mudou depois dela e a Company está aberta. `cancelar_pedido` e `alterar_pedido` só valem com o Order `closed`; depois do preparo o erro manda oferecer Handoff. Alterar reabre o Order e exige nova Recap ([operations.md](operations.md#cancelamento-alteração-e-estorno-de-pix)). |
| `status_pedido` | Pack `catalog_orders` | Estado do Order mais recente do Contact. |

Todo acesso das Tools é escopado pelo `ToolContext`: Catalog Items e Delivery Zones pelo `company_id`, o Order pela `conversation_id`, o histórico pelo `contact_id`. Para criar Tools de outro ramo, veja [packs.md](packs.md).

## Memória

Três camadas ([ADR 0003](adr/0003-memory-window-summary-fts.md)); a Recent Window é por Session, as outras duas por Conversation. Os limites vêm de `app/core/config.py` e podem ser trocados por variável de ambiente.

| Camada | Parâmetro | Padrão | Como funciona |
|---|---|---|---|
| Recent Window | `MEMORY_WINDOW` | 20 | As últimas 20 Messages de texto **da Session atual**, em ordem cronológica. Messages seguidas do mesmo papel viram uma só e a primeira é sempre `user`. |
| Summary | `SUMMARY_EVERY` | 20 | Quando há 20 Messages fora da janela ainda não resumidas, o modelo une o Summary anterior a elas (até 1200 caracteres, lotes de no máximo 100). |
| History Search | `HISTORY_SEARCH_LIMIT` | 8 | Tool `buscar_historico`: full-text search do Postgres (`portuguese`) nas Messages do Contact dentro da Instance. |

- O Summary é atualizado **depois** que a resposta já foi enviada (`executor.refresh_summary`, tarefa de fundo do worker com Session própria). Falha só vai para o log; o próximo Turn tenta de novo.
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
- **Agent**: `PUT /companies/{id}/agent` com `temperature` (0 a 1; `null` usa a do Gateway) e `max_tokens` (100 a 4000). O executor passa os dois ao modelo em cada chamada do Turn.

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
