# Operação: Handoff, Tickets e troubleshooting

Termos conforme o [glossário](../CONTEXT.md). Setup inicial em [setup.md](setup.md); o caminho de uma Message em [architecture.md](architecture.md).

## Handoff e Tickets

Handoff é a passagem da Conversation do Agent para um Attendant. Enquanto vale, o Agent não responde. O estado mora em `Conversation` (`human_in_loop`, `human_handoff_reason`, `ticket_id`); quem atende fica em `Ticket.assigned_to`.

### Como o Handoff começa

- **Pelo Agent.** O modelo chama `transferir_atendente(motivo, frase_empatica)`; só `motivo` é obrigatório, e sem `frase_empatica` a resposta é só a frase do sistema. A Tool abre um Ticket (`status=open`, `reason`, `content` com a última Message do Contact), liga `human_in_loop`, grava `human_handoff_reason` e `ticket_id`, publica `human_handoff_requested` e **encerra o Turn**. A resposta ao Contact é a `frase_empatica` escrita pelo Agent (coerente com o motivo) seguida de uma frase do sistema: "em instantes alguém continua" dentro do horário da Company, ou "fora do horário, um atendente continua hoje/amanhã/<dia> às HH:MM" fora dele (próxima janela de `Company.business_hours`, no fuso da Company). Sem horários cadastrados, vale sempre a frase de horário comercial. Se a Conversation já está em Handoff com Ticket, não abre outro.
- **Por um Attendant.** O botão "Assumir" do chat chama `POST /api/v1/conversations/{id}/take-control` (corpo opcional `{"reason": "..."}`). Com Ticket aberto, atribui-o ao usuário (`in_progress`); sem Ticket, abre um já atribuído. Se **outro** Attendant já está com a Conversation, responde **409**; o mesmo Attendant clicando de novo é idempotente (200).

O gate é lido do banco a cada Turn e de novo antes de enviar a resposta: se um Attendant assume enquanto o modelo ainda está respondendo, a resposta do Agent é descartada.

### Como o Handoff termina

- **Devolver.** O botão "Devolver ao Agent" chama `POST /api/v1/conversations/{id}/release-control`: desliga `human_in_loop`, limpa `ticket_id` e **fecha o Ticket** (`closed`, com `closed_at`). O Agent volta a responder na próxima Message. Sem Handoff em curso, ou se o timeout devolveu antes, a rota não muda nada e não anuncia nada.
- **Timeout.** `Company.handoff_timeout_hours` (padrão 4, de 1 a 720; editável em `PUT /companies/{id}` ou no painel) é o tempo sem Attendant agir. A contagem parte da abertura do Ticket e reinicia a cada ação do Attendant (assumir, escrever pelo painel, pelo Socket.IO ou pelo celular da Company; o eco `fromMe` de uma resposta do próprio Agent não conta). Vencido, a Conversation volta ao Agent e o Ticket vira `expired` (com `closed_at`). Quem executa: o worker (`sweep_forever`, a cada `HANDOFF_SWEEP_INTERVAL_SECONDS`, padrão 60) e, como rede de segurança exata, o consumer na próxima Message do Contact. Devolver e expirar são `UPDATE` condicionais (`WHERE human_in_loop`): se API e sweeper correm juntos, só um muda a linha e só ele publica `handoff_updated`; um Ticket `closed` nunca vira `expired`.
- Tickets `closed` e `expired` não reabrem. Uma nova transferência abre outro Ticket.

Toda mudança (assumir, devolver, expirar) publica `handoff_updated`; o chat atualiza os botões em tempo real e o estado vem de `human_in_loop` e `handoff_assigned_to` em `GET /conversations`, então sobrevive a reload.

### Atender

1. Veja os Handoffs abertos: `GET /api/v1/tickets?status=open`, ou o selo "Atendimento humano" na lista de conversas.
2. Assuma pelo botão "Assumir" (ou `take-control`). Esse é o único caminho de assumir; as rotas de Ticket são só de leitura.
3. Responda pelo dashboard ou por `POST /api/v1/conversations/{id}/messages` (a Instance precisa estar `connected`).
4. Clique em "Devolver ao Agent" (ou `release-control`). Isso fecha o Ticket e devolve a Conversation ao Agent.

### Ticket

| Campo | Significado |
|---|---|
| `status` | `open`, `in_progress`, `closed` (devolvido por um Attendant) ou `expired` (timeout). |
| `reason` | Motivo informado pelo Agent. |
| `content` | Última Message do Contact antes do Handoff. |
| `assigned_to` | Usuário (Attendant) responsável. |
| `attendant_activity_at` | Última ação do Attendant; base do timeout. |
| `closed_at` | Quando foi devolvido ou expirou. |
| `agent_type` | Sempre `whatsapp_agent` hoje; o filtro por `sales`/`sac` é resto do desenho antigo. |

`GET /tickets` aceita `status`, `agent_type`, `assigned_to`, `skip` e `limit` (máx. 100) e lista só os Tickets das Instances do usuário (superusuário: todos). `GET /tickets/{id}` de um Ticket de outra Instance responde 404. Ticket só se lê por ali: não existe `PATCH` nem `assign`, o único caminho de assumir e devolver é `take-control` / `release-control` da Conversation (UPDATE condicional; outro Attendant com a Conversation recebe 409). `GET /conversations/{id}/human-control-status` só lê: mostra o estado atual e `timeout_due` (o prazo venceu e o worker vai devolver); não muda nada.

### Limites conhecidos

- Não há Handoff automático quando um Attendant escreve pelo celular; só "Assumir" (`take-control`) ou a Tool ligam o estado. Escrever pelo celular durante um Handoff apenas reinicia o timeout.
- Sem o worker rodando, o timeout só é aplicado quando o Contact escreve de novo. `GET .../human-control-status` não aplica o timeout; só informa `timeout_due`.

## Cancelamento, alteração e estorno de Pix

O Contact cancela ou altera um Order sem Handoff enquanto ele está `closed` ("recebido, aguardando preparo") e foi confirmado na Session atual ou na anterior. Quando o Order passa para `in_production` (ou `sent`/`delivered`), ou é mais antigo, as Tools recusam e o Agent oferece Handoff com o motivo. Quem move o Order para `in_production` é a Company, pelo painel de Pedidos ([abaixo](#painel-de-pedidos-status-pela-company)).

- **Cancelar** (`cancelar_pedido`): o Order vira `cancelled`, com `cancelled_at` e `cancel_reason`. O Pix válido vira `cancelled`. Com um pedido em montagem e outro já confirmado, a Tool pede que o Agent pergunte qual; o confirmado se cancela com `numero`.
- **Alterar** (`alterar_pedido`): o Order volta a `ready_for_confirmation` com a Recap zerada e o estado confirmado guardado em `confirmed_snapshot`; o fechamento passa de novo por `recapitular` e pela confirmação do Contact. O Pix válido vira `superseded` e o `finalizar` seguinte gera outro com o total novo e um `txid` diferente (sufixo `R<revisão>`, até 25 alfanuméricos). Nunca há dois Pix válidos para o mesmo Order (índice único parcial `uq_payment_records_order_pix`, só `pending`/`paid`). Se a Session acaba sem a reconfirmação, o Order volta ao estado confirmado e o Pix original volta a valer ([ADR 0007](adr/0007-session-de-atendimento.md)).
- **Estorno manual**: o sistema não detecta pagamento (nada marca um Pix como `paid`), então todo Pix invalidado entra na lista da Company. `refund_status="pending"`: o Pix estava `paid`, devolver. `"verify"`: estava `pending`, mas o Contact pode ter pago; conferir no banco. `"refunded"` e `"dismissed"` são as baixas (devolvido; conferido, nada a devolver).
- **API**: `GET /api/v1/orders/refunds` lista os abertos (`pending` e `verify`) das Instances do usuário. `POST /orders/refunds/{id}/refunded` e `POST /orders/refunds/{id}/dismissed` dão a baixa e são idempotentes: repetir devolve 200 com o mesmo corpo, sem regravar. A baixa contrária à já dada é 409. Fora do escopo do usuário é 404; sem token, 401.

## Painel de Pedidos: status pela Company

A Company acompanha os Orders confirmados em **Pedidos** (`/pedidos`) e move o status; o Contact recebe uma Message curta no WhatsApp a cada mudança.

- **Transições** (`services/order_status.py`): `closed` (recebido) → `in_production` (em preparo) → `sent` (saiu para entrega) → `delivered` (entregue). A Company também cancela (`cancelled`) um Order `closed` ou `in_production`. Qualquer outra mudança, inclusive repetir o status atual, é 409 e não envia nada. `sent` e `delivered` não cancelam: só por Handoff.
- **Order em alteração**: o Order que o Contact reabriu com `alterar_pedido` aparece como "em alteração, aguardando nova confirmação" e não se move (409) até ser reconfirmado.
- **Cancelamento pela Company** reaproveita `changes.cancel_order`, o mesmo caminho do Contact: o Pix válido é invalidado e entra na lista de estornos (`pending`/`verify`). O aviso ao Contact menciona o estorno só se havia Pix.
- **Aviso ao Contact**: enviado por `whatsapp/sender.send_and_persist(sent_by="system")`, então fica gravado como Message `from_me` na Conversation, marcada em `messages.sent_by`. Falha no envio não desfaz a mudança: é logada (`Failed to notify the Contact about the Order status`) e a resposta traz `notification: {sent: false, error}`; o painel mostra um aviso amarelo. A Company não é avisada de novo: ela precisa falar com o Contact.
- **Eco do aviso**: o eco `fromMe` do aviso nunca é atividade de Attendant (não reinicia o timeout do Handoff, #35) nem uma segunda Message. Com id da Evolution, o dedup por `message_id` basta. Sem id, o aviso fica gravado com `message_id` NULL e o consumer reconhece o eco no banco (`whatsapp/sent_echo.adopt_echo`: Instance + JID + texto + janela de 2 min) e grava o id nele. Vale entre processos (API grava, worker consome). A resposta do Agent sem id segue a mesma regra (#92).
- **Concorrência**: a troca de status é um `UPDATE ... WHERE id = :id AND status = :lido` (`changes.claim_status`), no painel, no `cancelar_pedido` e no `alterar_pedido` do Contact. Quem perde a corrida não grava nada, não invalida Pix e não avisa ninguém: no painel é 409, na Tool é erro para o Agent (se a Company já passou o Order para preparo, o erro manda oferecer Handoff).
- **API**: `GET /api/v1/orders?status=active|done|all&offset=&limit=` (padrão `active`, `limit` 50, até 200) lista os Orders confirmados do mais recente ao mais antigo e devolve `{orders, total}`. `active` são recebido, em preparo, saiu para entrega e os reabertos em alteração; `done` são entregue e cancelado. Cada linha traz `allowed_transitions`, itens, total, pagamento e `refund_status` (uma consulta agrupada por página). `POST /api/v1/orders/{id}/status` com `{"status": "in_production" | "sent" | "delivered" | "cancelled"}` devolve `{order, notification}`. Escopo pelas Instances do usuário: Order de outra Company é 404; sem token, 401; status fora dessa lista, 422; transição inválida ou perdida numa corrida, 409.
- **"Cadê meu pedido"**: `status_pedido` lê o mesmo `Order.status`, então já reflete a mudança no próximo Turn.

## Troubleshooting

Os logs são estruturados (`structlog`). API e worker são processos separados: procure no log certo.

### O Agent não responde

Siga a ordem; o primeiro que bater é a causa. Mensagens em `código` aparecem no log do **worker**.

| Sintoma no log | Causa | Correção |
|---|---|---|
| Nada: nenhuma linha `Processing webhook event` | O webhook não chega à fila ou o worker está parado. | Veja as duas linhas abaixo. |
| `Message for unknown instance discarded` | Não há Instance com `evolution_instance_id` igual ao nome na Evolution. | Crie a Instance por `POST /api/v1/instances/{nome}` (é a única rota que grava a linha local) e tente de novo. |
| `Broadcast message ignored` | Lista de transmissão (`@broadcast`, inclui `status@broadcast`). A Message é descartada antes de ser gravada. | Esperado: nada fica no banco. Grupos (`@g.us`) são gravados, mas o Agent não os atende (`Message not processed by agent` com `reason=group`). |
| `Invisible message type skipped` | Protocolo, reação, enquete, edição ou payload sem conteúdo. | Esperado: não vira linha de Message. |
| `Message not processed by agent` com `reason=from_me` | Mensagem enviada pelo próprio número. | Esperado. |
| `reason=unresolved_lid` | JID `@lid` sem número real: não há como responder. | Esperado; aguarde o Contact aparecer com número. |
| `reason=stale` | Mensagem mais velha que 5 min em relação ao início do worker (backlog de uma queda). | Esperado; fica gravada, sem resposta. |
| `Agent disabled for this instance` | `agent_enabled=false` na Instance. | `PATCH /instances/{nome}/agent-status` com `{"agent_enabled": true}`. |
| `No active Agent for this Instance or its Company` | A Company não tem Agent ativo. | `python scripts/seed_data.py` (cria um por Company e liga as Instances). Aparece uma vez por Instance até o worker reiniciar. |
| `Instance has no Company, Agent cannot run` | `instances.company_id` nulo: Instance criada antes de a API gravar a Company. | Um superusuário com Company chama `POST /api/v1/instances/{nome}`: assume a Instance e grava a Company dele. Veja [setup.md](setup.md#ligar-a-instance-à-company-e-ao-agent). |
| `Conversation in Handoff, Agent stays silent` | A Conversation está em Handoff. | Atenda e clique em "Devolver ao Agent" (`release-control`), ou espere o timeout (veja acima). |
| `Turn failed` e o Contact recebe "Desculpe, tive um problema…" | Exceção dentro do Turn; o stack trace vem logo antes. | Causas comuns abaixo. |
| `Unexpected error processing message with agent` com `EvolutionAPIError` logo depois de `Turn finished` | O Turn rodou, mas o envio pela Evolution falhou: Instance não conectada ao WhatsApp, Evolution fora do ar ou `EVOLUTION_API_URL`/`EVOLUTION_API_KEY` errados. A Message do Contact fica gravada e `pending` (`failed`); a recuperação a retoma depois de `TURN_CLAIM_LEASE_SECONDS`, até `TURN_RECOVERY_MAX_AGE_SECONDS`, quando vira `skipped: stale`. | Conecte a Instance (QR code) e confira `GET {EVOLUTION_API_URL}/instance/fetchInstances` com o header `apikey`. |

Um Turn que passa de `TURN_TIMEOUT_SECONDS` (padrão 90 s) sai do loop com `Turn timed out` no log (sem stack trace) e o Contact recebe a mesma resposta de erro. A Tool que passa de `TOOL_TIMEOUT_SECONDS` aparece como `Tool handler timed out` e o Turn continua sem ela. Veja [Prazos e retries](agent.md#prazos-e-retries).

Causas comuns de `Turn failed`:

- `LLMNotConfiguredError: Nenhum Gateway atribuido…`: nenhum modelo atribuído a `whatsapp_agent` nem a `default`. Atribua em **Configurações > Gateways**.
- `LLMNotConfiguredError` com a chave do Gateway: a chave não abre. A `GATEWAY_ENCRYPTION_KEY` mudou, ou o banco ainda tem chaves criptografadas com a `SECRET_KEY` (antes da chave própria); rode `python scripts/reencrypt_gateway_secrets.py` (passo único, veja [Atualizar um banco existente](#atualizar-um-banco-existente-chaves-de-gateway)) ou regrave a chave do Gateway.
- `LLMProviderError`: o Gateway respondeu fora do formato, deu 5xx ou estourou o timeout (60 s por padrão por chamada). Os retries (timeout, 429, 5xx) saem de um orçamento por Turn (`TURN_RETRY_BUDGET`, `TURN_RETRY_WAIT_SECONDS`) e respeitam `Retry-After`; acabou o orçamento, o erro sobe. Teste com `POST /gateways/models/{id}/test`.
- Gateway em `localhost` com a API em container: dentro do container use `http://host.docker.internal:<porta>`.

### O pedido não fecha

O `finalizar` recusa em código, e o Agent repassa o motivo ao Contact. Os erros que aparecem no `tool_result` (visível em `tool_event`):

| Erro | Causa | O que fazer |
|---|---|---|
| "A empresa está fechada agora… Abre hoje às 18:00" | `Company.business_hours` diz fechado no fuso da Company. | Confira horários e `timezone` em Configurações > Geral. O Order fica salvo. |
| "O cliente ainda não viu a recapitulação" / "A recapitulação ainda não chegou ao cliente" | Faltou `recapitular`, ou a resposta com a Recap não foi enviada (Turn falhou, Handoff, Evolution fora). | Nada: o Agent recapitula de novo e espera o "confirmo". |
| "O pedido mudou depois da recapitulação" | Item, endereço, pagamento ou troco mudou depois da Recap. | Nada: nova Recap e nova confirmação. |
| "Pedido mínimo de R$ …" | Itens abaixo de `minimum_order` (sem a taxa). | Ajuste o mínimo no painel, se for o caso. |
| "Esta empresa não tem chave Pix cadastrada" | `pix_key` vazio e o Contact escolheu Pix. | Cadastre a chave em Configurações > Geral. |

### A Evolution reinicia em loop

- **`P1000 Authentication failed … credentials for evolution`** no log do `evolution-api`: o usuário e o banco `evolution` não existem porque o `scripts/init-multiple-databases.sh` não rodou. Ele só roda na primeira criação do volume do Postgres, e só se o Docker conseguir montá-lo como arquivo. Com Colima, mantenha o repositório dentro do `$HOME`. Depois de corrigir o caminho, recrie o volume (**apaga os dados locais do Postgres**): `docker compose --env-file backend/.env down -v && docker compose --env-file backend/.env up -d`.
- **`required variable EVOLUTION_API_KEY is missing`** ao subir o compose: faltou `--env-file backend/.env` ou a variável está vazia no `.env`.
- **`Permission denied` ao gravar em `/evolution/instances` ou `/evolution/store`** (a Evolution cai logo depois do start): os volumes foram criados pelo compose antigo, com dono root, e a imagem nova roda como uid 1000. Rode uma vez o `chown` de [setup.md](setup.md#2-infra-postgresql-redis-rabbitmq-evolution) ("Migrando de um compose antigo"):
  `docker compose --env-file backend/.env run --rm --no-deps --build --user root --entrypoint chown evolution-api -R node:node /evolution/instances /evolution/store`.

### O webhook não chega à fila

- **401 no webhook**: o token da URL não bate com `EVOLUTION_WEBHOOK_TOKEN` do `backend/.env`, ou a variável está vazia ([ADR 0006](adr/0006-webhook-token-auth.md)). Confira `WEBHOOK_GLOBAL_URL` no serviço `evolution-api` e se o compose foi subido com `--env-file backend/.env`.
- **Token chega como `TOKEN/messages-upsert`**: o serviço da Evolution está com `WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=true`. Ponha `false` (motivo em [setup.md](setup.md#2-infra-postgresql-redis-rabbitmq-evolution)).
- **A Evolution não alcança a API**: no Linux o container precisa de `extra_hosts: host.docker.internal:host-gateway` e a API de `--host 0.0.0.0`.
- **A fila cresce e nada consome**: o worker não está rodando (`python scripts/run_worker.py`). Veja a fila `webhooks.evolution` no painel do RabbitMQ (`http://localhost:15672`, vhost `neuralilux`, usuário e senha de dev do compose) ou rode `python scripts/queue_admin.py status`. A fila guarda até 24 h e 100 mil Messages; o que passa disso ou vence o TTL vai para a dead-letter queue (próxima seção), não some.
- Uma Message cujo processamento falha volta à fila **uma vez**; se falhar de novo (ou for JSON inválido), vai para a dead-letter queue e é logada em `error` (`Processing error on redelivery, sent to the dead-letter queue`).

### Dead-letter queue do webhook

A fila `webhooks.evolution` tem uma exchange de dead-letter (`webhooks.evolution.dlx`) e uma fila `webhooks.evolution.dlq`. Chega lá, com o motivo no cabeçalho `x-death`:

- **`rejected`**: o consumer falhou duas vezes na mesma mensagem (a original e a reentrega) ou o corpo não é JSON. Duas vezes, e não uma, porque uma falha isolada costuma ser passageira (banco fora, deadlock); `redelivered` do broker conta a segunda sem exigir fila quorum (`x-delivery-count`), e o consumer é idempotente por `Message.message_id`, então a reentrega é segura.
- **`expired`**: a mensagem passou 24 h na fila sem ser consumida (worker parado).
- **`maxlen`**: a fila passou de 100 mil mensagens. O overflow é `drop-head`: a **mais antiga** vai para a DLQ e a nova entra. O publish nunca falha por fila cheia, então o webhook não responde 503 nem a Evolution reenvia o que já está guardado. Com o `ack` logo depois de gravar a Message (#91), a fila só enche com o worker parado ou travado.

A DLQ guarda até 100 mil mensagens; passando disso, as mais antigas dela somem. Alerte pela profundidade (`status`) ou pelo painel.

**Inspecionar** (a partir de `backend/`, com o `RABBITMQ_URL` do `.env`):

```bash
python scripts/queue_admin.py status           # mensagens e consumers da fila e da DLQ
python scripts/queue_admin.py peek --limit 10  # evento, instância, motivo e hora de cada uma; não remove
```

O painel do RabbitMQ (`Queues` → `webhooks.evolution.dlq` → `Get messages`, com `Ack mode: Reject requeue true`) mostra o corpo completo.

**Reprocessar** depois de corrigir a causa (o log do worker traz o erro):

```bash
python scripts/queue_admin.py replay --limit 1   # teste com uma
python scripts/queue_admin.py replay             # toda a DLQ
```

Cada mensagem só sai da DLQ depois que a fila principal confirmou o recebimento. Se o `replay` cair no meio, no máximo uma mensagem fica duplicada, e o consumer a ignora (dedup por `Message.message_id`). O `replay` move só o que estava na DLQ ao começar: uma mensagem que falhar de novo volta para a DLQ em vez de girar. Mensagem `expired` com mais de 5 minutos é gravada mas não ganha Turn (`stale`): o histórico se recupera, a resposta não. Para descartar a DLQ inteira, apague as mensagens no painel (`Purge Messages`).

### Migrar a fila de um ambiente existente (DLQ)

O RabbitMQ não deixa mudar os argumentos de uma fila que já existe: com `webhooks.evolution` criada antes da DLQ, a app e o worker **não sobem** (`PRECONDITION_FAILED`, log `Queue exists with other arguments: migrate it`). Passo único, **antes de subir a nova versão**:

1. Pare a API e o worker (a janela dura segundos; o webhook responde 503 e a Evolution reenvia).
2. `cd backend && python scripts/queue_admin.py migrate`.
3. Suba a API e o worker.

O `migrate` cria a exchange e a DLQ, move as mensagens para uma fila temporária `webhooks.evolution.migrating`, apaga a fila antiga (só se estiver vazia), recria a fila com os argumentos novos e devolve as mensagens em ordem, confirmando cada uma no destino antes de tirá-la da origem. Imprime `migrated`, `moved_out` e `moved_back`. É idempotente: sem nada a migrar devolve `migrated: false`; se foi interrompido no meio, rodar de novo esvazia a temporária na fila nova. Um ambiente novo não precisa dele. Ele só mexe nas filas `webhooks.evolution*`. Para desfazê-lo, veja "Reverter a migração da fila".

O `migrate` e o `rollback` recusam (saem com código 1 e `recusado: ...` no stderr, sem mexer em nada) se a fila tem consumer ativo: pare a API e o worker antes. O `status` mostra os consumers.

### Reverter a migração da fila (rollback)

Voltar ao código anterior à DLQ depois do `migrate` falha: o código antigo declara `webhooks.evolution` sem DLX e o broker responde `PRECONDITION_FAILED`. O `rollback` é o inverso do `migrate`. Passo a passo:

1. Pare a API e o worker.
2. `cd backend && python scripts/queue_admin.py status`. Se a DLQ tiver mensagens, `python scripts/queue_admin.py replay` (devolve tudo à fila principal) ou descarte-as no painel (`Purge Messages`). O `rollback` **recusa** enquanto a DLQ não estiver vazia, porque o código antigo não a lê.
3. `python scripts/queue_admin.py rollback`.
4. Suba a versão antiga da API e do worker.

O `rollback` move as mensagens para a fila temporária `webhooks.evolution.rollingback`, apaga a fila (só se vazia), recria-a com os argumentos antigos (`x-message-ttl` e `x-max-length`, sem DLX nem `drop-head`) e devolve as mensagens em ordem, confirmando cada uma no destino antes de tirá-la da origem. Imprime `rolled_back`, `moved_out` e `moved_back`. É idempotente e retomável, como o `migrate`: sem nada a reverter devolve `rolled_back: false`; se foi interrompido, rodar de novo esvazia a temporária na fila recriada. A exchange `webhooks.evolution.dlx` e a `webhooks.evolution.dlq` (vazia) ficam no broker sem uso; apague-as no painel se quiser. Para migrar de novo, rode `migrate`.

As filas `whatsapp.messages.*`, `ai.processing` e `notifications`, que o código declarava mas ninguém publicava nem consumia, deixam de ser declaradas. As que já existem no broker ficam vazias e sem uso: apague-as no painel quando quiser.

### Instance e QR code

- **QR code não aparece**: confirme `CONFIG_SESSION_PHONE_VERSION` no serviço da Evolution e o limite de tentativas (`QRCODE_LIMIT=30`); reinicie a Instance (`DELETE /instances/{nome}/logout`, depois `POST /instances/{nome}/connect`).
- **`POST /instances/{nome}/connect` devolve `qr_code: null` e "already open"**: a Instance já está conectada; não há QR.
- **O status da Instance não atualiza**: o evento `connection.update` depende do webhook; veja a seção anterior.

### Dashboard sem eventos ao vivo

- `thinking_event`, `tool_event` e `human_handoff_requested` saem do **worker** pelo Redis: API e worker precisam usar o mesmo `REDIS_URL`. O chat consome `thinking_event` e `human_handoff_requested`; `tool_event` está disponível a quem entrar na sala da Conversation.
- **Redis lento ou fora**: o evento de UI nunca segura o Turn além de `REALTIME_PUBLISH_TIMEOUT_SECONDS` (1 s; o fechamento do cliente descartado roda em background) nem o derruba; o evento é perdido e logado (`Realtime event dropped`). Depois de uma falha, os eventos seguintes são descartados por `REALTIME_PUBLISH_COOLDOWN_SECONDS` (5 s) e o cliente reconecta do zero. O cooldown precisa ser maior que o teto: a app recusa subir se não for. O cliente usa `REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS`, `REDIS_SOCKET_TIMEOUT_SECONDS` e `REDIS_HEALTH_CHECK_INTERVAL_SECONDS`.
- **503 no webhook / `Evolution webhook event lost` no log**: o RabbitMQ recusou o publish. A Evolution reenvia o webhook (até 10 vezes, backoff até 300 s; detalhes em [evolution-data-formats.md](agents/evolution-data-formats.md)); o caminho websocket não reenvia.
- O socket autentica pelo cookie de sessão; sem ele, com sessão inválida/vencida ou de usuário inativo a conexão é recusada com `connect_error: unauthorized` (mesma regra da API HTTP) e o painel encerra a sessão. Qualquer outra falha de conexão é tratada como passageira: o painel avisa e reconecta sem limite. O cliente precisa chamar `subscribe_instance` e `join_conversation` com os UUIDs (`instanceId`, `conversationId`); depois de uma queda ele refaz as duas chamadas sozinho. Desativar o usuário recusa conexões novas e os eventos `subscribe_instance`, `join_conversation` e `send_message`, mas um socket já aberto segue recebendo os `emit` da sala até desconectar.
- Há polling de contingência no frontend para mensagens enquanto o socket está fora, mas não para esses eventos. Ao reconectar, o painel recarrega a lista, os contadores e as Messages da Conversation aberta.

### Login ou cadastro respondem 429 ou 503

`POST /auth/login` e `POST /auth/register` têm rate limit por IP, em janela fixa no Redis (a chave `neuralilux:ratelimit:<escopo>:<ip>` expira sozinha ao fim da janela):

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `LOGIN_RATE_LIMIT_ATTEMPTS` / `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | 10 / 60 | tentativas de login por IP por janela |
| `REGISTER_RATE_LIMIT_ATTEMPTS` / `REGISTER_RATE_LIMIT_WINDOW_SECONDS` | 5 / 3600 | tentativas de cadastro por IP por janela |
| `ALLOW_PUBLIC_REGISTRATION` | `false` | cadastro anônimo: `false` responde 403 |
| `TRUSTED_PROXIES` | vazio | proxies de confiança (JSON, IP ou CIDR) |

- **429**: passou do limite. `Retry-After` traz os segundos até a janela virar. Toda tentativa conta, acertando ou errando, e a senha de quem está bloqueado não é conferida. No cadastro, a tentativa recusada com 403 (cadastro fechado) também conta.
- **Redis fora do ar ou travado: falha fechada, 503.** Sem Redis não há como contar tentativas, e deixar o login passar sem contar abriria a força bruta justamente quando o contador cai. O preço é o login (e o cadastro público) indisponível enquanto o Redis cai, o que já derruba o resto do atendimento (eventos de UI, debounce). Um Redis que não responde não prende a requisição: o cliente usa `REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS` e `REDIS_SOCKET_TIMEOUT_SECONDS` e a chamada tem teto igual à soma dos dois. Quem já tem token segue usando a API; só login e cadastro param. O superusuário autenticado cadastra mesmo com o Redis fora, porque não passa pelo limite. O log traz `Rate limit failed closed: Redis unavailable or too slow; refusing the request` (com `error_type` e `error`); o cliente descartado é fechado em background e o novo reconecta sozinho na tentativa seguinte.
- **Redis 7.0 ou mais novo.** O contador usa `EXPIRE ... NX`, que só existe a partir do Redis 7.0 (o `docker-compose.example.yml` usa `redis:7.4`). Num Redis 6 ou anterior o comando é recusado e login e cadastro público respondem 503 sempre; o log então traz `Redis rejected the rate limit command (EXPIRE NX needs Redis >= 7.0)`. Atualize o Redis, não o limite.
- **Atrás de proxy reverso**: o IP do peer TCP é o do proxy, e sem configuração todos os clientes dividem um contador (o primeiro a abusar bloqueia todos). Liste os proxies em `TRUSTED_PROXIES`; só de um peer listado o `X-Forwarded-For` é lido (todas as linhas do cabeçalho, em ordem, da direita para a esquerda), pulando os proxies listados, e o primeiro endereço fora da lista vira o IP do cliente. O proxy precisa **anexar** o IP real ao cabeçalho (nginx: `proxy_add_x_forwarded_for`) e nunca repassar o valor do cliente. Valor que não é IP no cabeçalho é ignorado e vale o IP do peer. Sem `TRUSTED_PROXIES`, o cabeçalho é ignorado por inteiro, então um cliente não escolhe a própria chave.
- **`FORWARDED_ALLOW_IPS` nunca `*`.** O uvicorn também lê o `X-Forwarded-For` (`--proxy-headers`, ligado por padrão) e reescreve o IP do peer para quem estiver em `FORWARDED_ALLOW_IPS` (padrão `127.0.0.1`). Com `*`, qualquer cliente forja o próprio IP e escapa do limite. Com o proxy em loopback e o uvicorn no padrão, o uvicorn já consome o cabeçalho e entrega o IP real como peer: nesse caso deixe `TRUSTED_PROXIES` vazio, porque o peer que a app enxerga já é o cliente. Preencha `TRUSTED_PROXIES` quando o uvicorn não reescreve o peer (proxy em outro host ou `--no-proxy-headers`).
- **IPv6 conta por /64.** Um cliente IPv6 recebe pelo menos um /64; trocar o sufixo do endereço não zera o contador. IPv4 mapeado em IPv6 (`::ffff:a.b.c.d`) conta como o IPv4.
- Para liberar alguém bloqueado antes da janela virar: `redis-cli DEL neuralilux:ratelimit:login:<ip>` (para IPv6, `<ip>` é o prefixo, por exemplo `2001:db8:1:2::/64`).

### Rotacionar a `EVOLUTION_API_KEY` ao publicar o #85

Antes do #85, `POST /instances/{nome}` criava a Instance na Evolution com a `EVOLUTION_API_KEY` global como token da Instance, e a resposta devolvia o retorno da Evolution (campo `raw`, com `hash` = o token). Qualquer usuário que criou uma Instance recebeu a chave global. A partir do #85 cada Instance nasce com token próprio aleatório e a resposta não traz mais o retorno da Evolution, mas **as Instances que já existem continuam com a chave global como token e a chave já foi exposta**. No deploy:

1. Gere uma chave nova e troque `EVOLUTION_API_KEY` em `backend/.env` (a Evolution lê o mesmo valor como `AUTHENTICATION_API_KEY`, pelo `docker-compose.example.yml`). API e worker leem o mesmo arquivo.
2. Reinicie Evolution, API e worker.
3. As Instances antigas passam a ter um token que não vale mais nada; a app usa só a chave global no header `apikey`, então o atendimento segue. Recrie as Instances que precisem de token próprio.

### A app não sobe

- `Configuração recusada com ENVIRONMENT='production' (sem ENVIRONMENT definido vale 'production')…`: sem `ENVIRONMENT=development` explícito a app recusa `SECRET_KEY`, `EVOLUTION_WEBHOOK_TOKEN` e `GATEWAY_ENCRYPTION_KEY` vazios ou de exemplo (e exige `GATEWAY_ENCRYPTION_KEY` diferente da `SECRET_KEY`, as duas com 32+ caracteres). Em dev local, ponha `ENVIRONMENT=development` no `backend/.env`. Fora dele, defina valores fortes e distintos (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`).
- Erro de migração com mais de uma head: veja [agents/migrations.md](agents/migrations.md).
- O worker sai com `Failed to connect to RabbitMQ`: confira `RABBITMQ_URL`, o vhost `neuralilux` e `docker compose --env-file backend/.env ps`.
- Em containers (perfil `app`): `api` e `worker` ficam em `Created` e nunca iniciam quando o `migrate` falhou. Veja `docker compose --env-file backend/.env --profile app logs migrate`.

### Atualizar um banco existente: chaves de Gateway

Passo único e obrigatório ao atualizar um banco que já tem Gateways com chave de API, **antes de subir a app**:

1. Backup, **fora do repositório** (o dump contém os tokens): `mkdir -p ~/backups && pg_dump -t inference_gateways "$DATABASE_URL" > ~/backups/inference_gateways.sql` (URL `postgresql://…`, sem o `+psycopg`). O script regrava os tokens e não tem volta.
2. No `backend/.env`, defina `GATEWAY_ENCRYPTION_KEY` (valor **real**, com 32+ caracteres e diferente da `SECRET_KEY`) e mantenha a `SECRET_KEY` atual. Com a chave vazia ou de exemplo o script recusa rodar (exit 1) e não altera nada, mesmo em `development`.
3. `cd backend && python scripts/reencrypt_gateway_secrets.py`. Imprime quantas chaves converteu.

O script abre cada chave com a `SECRET_KEY` (HKDF ou SHA-256 antigo) e regrava com a `GATEWAY_ENCRYPTION_KEY`. Idempotente: a segunda execução imprime 0 e não altera nada. Chaves que nenhuma das duas abre ficam intactas (regrave-as pela API). Depois disso a `SECRET_KEY` pode ser rotacionada sem tocar nos Gateways; já trocar a `GATEWAY_ENCRYPTION_KEY` invalida as chaves salvas. Só o script re-criptografa; seed, API e worker nunca mexem nos tokens.

### Containers (perfil `app`)

Como subir e o que cada serviço faz: [setup.md](setup.md#api-worker-e-painel-em-containers). Aqui, a operação.

- **Quem roda como quê.** `api`, `worker` e `migrate` usam a mesma imagem (`neuralilux/backend`, uid 10001); o painel e a Evolution rodam como uid 1000. Confira com `docker compose --env-file backend/.env --profile app top`. PostgreSQL, Redis e RabbitMQ usam as imagens oficiais, que largam o root depois de ajustar permissões.
- **Logs.** `docker compose --env-file backend/.env --profile app logs -f api worker`. API e worker são processos separados, como no modo host.
- **Parar o worker.** `docker compose ... stop worker` manda SIGTERM e espera até 30 s (`stop_grace_period`). O worker para de consumir, espera os Turns em voo até `SHUTDOWN_TIMEOUT_SECONDS` (padrão 20 s, prazo único que não espera `TURN_TIMEOUT_SECONDS`), cancela o que sobrar (a Message fica `pending` e o worker seguinte a retoma) e desconecta: pior caso ~25 s. **Regra:** `stop_grace_period` ≥ `SHUTDOWN_TIMEOUT_SECONDS` + 10 s. Se subir o prazo, suba o `stop_grace_period` do compose junto; senão o Docker mata o worker com SIGKILL no meio do desligamento.
- **Healthcheck.** `api` e painel têm `HEALTHCHECK` na imagem (`/health` e `/login`). O worker não escuta porta e o `migrate` sai ao terminar; os dois têm o healthcheck desligado no compose.
- **Login não "gruda" no painel.** `ENVIRONMENT` ausente vale `production`, e o cookie `nlx_auth` leva `Secure`: o navegador o descarta em HTTP puro fora de `localhost`. Acesse por `localhost`, ponha TLS na frente ou use `ENVIRONMENT=development` só em ambiente local. Mutação com 403: a origem do painel não está em `CORS_ORIGINS`.
- **Painel chama a API errada.** `NEXT_PUBLIC_API_URL` é gravada no bundle no build. Troque no `.env` e reconstrua: `docker compose ... --profile app up -d --build frontend`. `API_INTERNAL_URL` não precisa de rebuild.
- **Scripts de manutenção** rodam no container da API, com o mesmo ambiente: `docker compose --env-file backend/.env --profile app run --rm api python scripts/<script>.py`. Para variáveis extras, `-e NOME=valor`.

### Migrações em banco já em uso: janela de manutenção

No perfil `app`, o serviço `migrate` roda `alembic upgrade head` a cada `up`, e `api` e `worker` só iniciam depois dele. Num banco **novo** isso basta. Num banco **em uso**, a migração `0015` (fusão de Contacts e Conversations duplicados, índices em `messages` e `UNIQUE` em `contacts`/`conversations`) pede janela de manutenção ([agents/migrations.md](agents/migrations.md#0015-fusão-de-duplicatas-e-janela-de-manutenção)): os `ADD CONSTRAINT UNIQUE` seguram `ACCESS EXCLUSIVE` até o commit, e uma API no ar pode recriar uma duplicata e derrubar a migração. O tempo cresce com o tamanho de `messages`.

1. Pare quem escreve no banco: `docker compose --env-file backend/.env --profile app stop api worker` (no modo host, pare o `uvicorn` e o `run_worker.py`).
2. Faça backup do banco, **fora do repositório** (o dump tem dados de clientes e tokens): `mkdir -p ~/backups && docker compose --env-file backend/.env exec -T postgres pg_dump -U neuralilux neuralilux > ~/backups/neuralilux-$(date +%F).sql`.
3. Migre: `docker compose --env-file backend/.env --profile app run --rm migrate` (ou `alembic upgrade head` no host).
4. Se o banco ainda tem Gateways com chave criptografada pela `SECRET_KEY`, rode o passo [Atualizar um banco existente](#atualizar-um-banco-existente-chaves-de-gateway) **antes de subir a app**. No container: `docker compose --env-file backend/.env --profile app run --rm api python scripts/reencrypt_gateway_secrets.py`, com o backup de `inference_gateways` feito antes (o script regrava os tokens e não tem volta). `SECRET_KEY` e `GATEWAY_ENCRYPTION_KEY` precisam estar no `backend/.env`.
5. Suba de novo: `docker compose --env-file backend/.env --profile app up -d`.

### Agrupamento, concorrência e prefetch

A entrega do RabbitMQ só grava a Message e confirma (`ack`); o Turn roda depois, numa task do worker. Por isso o `RABBITMQ_PREFETCH` (padrão 8) limita só quantas Messages estão sendo **gravadas** ao mesmo tempo, e um Gateway lento não atrasa um `connection.update` nem a gravação das Messages seguintes.

- **Concorrência dos Turns.** `TURN_CONCURRENCY` (padrão 8) é o máximo de Turns falando com o Gateway ao mesmo tempo por worker. A pausa do debounce (`DEBOUNCE_SECONDS`, 3 s) não ocupa vaga. Os Turns acima do limite esperam, com a Message `pending` no banco. Suba o valor se o Gateway aguenta mais paralelismo; o pool do banco (`pool_size=10`, `max_overflow=20` em `app/core/database.py`) precisa acompanhar, porque cada Turn abre a própria Session e a segura até a resposta sair. Cada Turn também segura uma conexão do pool de locks (ver "Réplicas do worker").
- **Desligar o agrupamento.** `DEBOUNCE_SECONDS=0` volta a um Turn por Message.
- **Sintoma de Turns acumulando.** Resposta atrasada com o Gateway lento: veja quantas Messages estão `pending` (consulta abaixo) e ajuste `TURN_CONCURRENCY`.
- **Sem teto na fila local.** `TurnRunner` não limita as Messages esperando vaga nem as tasks: com o Gateway fora por muito tempo elas acumulam em memória. Uma Message nessa fila local é respondida por este processo mesmo depois de `TURN_RECOVERY_MAX_AGE_SECONDS`; a regra `stale` só vale na recuperação. O estado é durável (`pending` no banco), então reiniciar o worker esvazia a fila sem perder nada.

### Mensagens pendentes e recuperação

Garantia e estados: [architecture.md](architecture.md#resposta-durável). Variáveis (todas em segundos, exceto `TURN_CONCURRENCY`). No perfil `app` do compose, `TURN_CONCURRENCY`, `TURN_RECOVERY_MAX_AGE_SECONDS`, `TURN_CLAIM_LEASE_SECONDS` e `SHUTDOWN_TIMEOUT_SECONDS` chegam do `backend/.env`; `TURN_RECOVERY_INTERVAL_SECONDS` fica no default:

| Variável | Padrão | Efeito |
|---|---|---|
| `TURN_CONCURRENCY` | 8 | Turns simultâneos por worker. |
| `TURN_RECOVERY_INTERVAL_SECONDS` | 60 | Intervalo da varredura de pendentes (também roda na subida). |
| `TURN_RECOVERY_MAX_AGE_SECONDS` | 900 | Idade máxima de uma pendente a ser retomada; mais velha vira `skipped: stale`. Responder meia hora depois seria estranho para o Contact. |
| `TURN_CLAIM_LEASE_SECONDS` | 180 | Quanto tempo a posse de um worker protege a Message de outro. Maior que `DEBOUNCE_MAX_WAIT_SECONDS + TURN_TIMEOUT_SECONDS`. |
| `SHUTDOWN_TIMEOUT_SECONDS` | 20 | Prazo do shutdown para os Turns em voo. |

- **Deploy e reinício.** O `SIGTERM` para de consumir, espera os Turns até `SHUTDOWN_TIMEOUT_SECONDS` e cancela o resto; as Messages desses Turns seguem `pending` e o worker novo as retoma na subida. A regra do `stop_grace_period` (≥ `SHUTDOWN_TIMEOUT_SECONDS` + 10 s) e o valor do compose estão em [Containers](#containers-perfil-app); fora do compose, aplique-a no seu orquestrador.
- **Vários workers.** Podem rodar juntos; veja "Réplicas do worker" abaixo. Um worker que cai sem `SIGTERM` (kill -9, falta de energia) deixa a Message com a posse até vencer em `TURN_CLAIM_LEASE_SECONDS`; só então outro a retoma. O Postgres solta os locks dele na hora, porque a conexão fecha.
- **Ver o que está pendente.** `SELECT turn_reason, count(*), min(timestamp) FROM messages WHERE turn_state = 'pending' GROUP BY 1;` (usa o índice parcial). Pendente antiga que não sai: o worker está parado, ou a Message passa de `TURN_RECOVERY_MAX_AGE_SECONDS` e vira `stale` na próxima varredura.
- **Duplicidade.** A garantia é pelo menos uma resposta; ver "Limites" em architecture.md para a janela em que um crash entre o envio e a gravação da resposta pode repetir a resposta.

### Réplicas do worker

Garantia (#92): em Postgres, **nunca há dois Turns da mesma Conversation ao mesmo tempo**, nem dois refreshes do Summary, em qualquer número de réplicas. Cada Message continua respondida uma vez (claim do #91), e o segundo Turn de uma rajada dividida entre réplicas já vê o que o primeiro respondeu. Desenho e mapa do que vive em memória: [architecture.md](architecture.md#vários-workers-e-locks-por-conversation).

- **Réplicas suportadas.** O desenho não tem teto fixo: o limite é o número de conexões do Postgres (conta abaixo). **Validado: 2 réplicas** (testes `tests/postgres/test_two_replicas.py` e o smoke do PR). Com mais de 2, faça a conta e confirme com o mesmo smoke.
- **Como escalar.** Suba outro `python scripts/run_worker.py` com o mesmo `.env` (mesmos `DATABASE_URL`, `RABBITMQ_URL`, `REDIS_URL`). O RabbitMQ reparte a fila `webhooks.evolution`; a recuperação e o sweeper de Handoff rodam em todas e são idempotentes. Não há líder nem configuração por réplica.
- **Só SQLite (dev, testes).** Sem Postgres o lock vale só dentro do processo: com SQLite rode **um** worker. É a mesma garantia de antes do #92.
- **Por que lock de sessão e conexão própria.** O Turn faz vários commits e fala com o Gateway por até `TURN_TIMEOUT_SECONDS`; um lock de transação exigiria uma transação aberta esse tempo todo. O lock de sessão segura **uma conexão parada** por bloco ativo, tirada de um pool separado (`LOCK_POOL_SIZE`): quem segura um lock precisa de uma conexão de dados para andar, e se os dois dividissem o pool, locks parados poderiam ocupá-lo inteiro e travar todos. Quem espera não segura conexão (tenta de novo a cada 0,2 s).
- **Conexões por worker.** No pior caso: pool de dados (10 + 20 de overflow) + `LOCK_POOL_SIZE` (32) = 62; a API soma mais 30. No uso normal sobram poucas: um lock `TURN` e um `SAVE` por Turn em voo (até `TURN_CONCURRENCY` = 8), um `SAVE` por webhook sendo gravado (até `RABBITMQ_PREFETCH` = 8) e um `SUMMARY` por refresh. Some `réplicas × 62 + 30` e compare com `max_connections` do Postgres (100 por padrão): com o padrão, 2 réplicas só cabem no pior caso se você baixar `LOCK_POOL_SIZE` ou os pools, ou subir `max_connections`. Pool de locks esgotado conta como "lock ocupado": o Turn espera, nunca bloqueia o loop.

| Variável | Padrão | Efeito |
|---|---|---|
| `LOCK_POOL_SIZE` | 32 | Conexões de lock por processo (sem overflow). Reduza junto com `TURN_CONCURRENCY` e `RABBITMQ_PREFETCH`. |
| `TURN_LOCK_WAIT_SECONDS` | 120 | Quanto um Turn espera o Turn de outra réplica da mesma Conversation. Não menor que `TURN_TIMEOUT_SECONDS`. Vencido, as Messages voltam a ficar sem dono e a recuperação as retoma (log `Conversation busy in another process`). |
| `LOCK_SAVE_WAIT_SECONDS` | 45 | Quanto o webhook e o envio esperam o lock de gravação do JID. Maior que o timeout de 30 s do envio pela Evolution. Vencido, a entrega falha e o RabbitMQ a entrega de novo. |

- **Sintomas.** `Conversation busy in another process, Messages handed back`: Turns de outra réplica estão passando de `TURN_LOCK_WAIT_SECONDS` (Gateway lento). `Summary refresh skipped: another process is refreshing`: esperado, o outro refresh cobre. `Messages of another process joined this Turn`: esperado, é a rajada dividida virando uma resposta só.

### Memória

- **O Agent esqueceu algo antigo**: só a Recent Window (cerca de 11 a 22 Messages da Session atual, cortada em blocos de `MEMORY_WINDOW_BLOCK`) entra literal; depois de uma pausa maior que `session_timeout_minutes` da Company (padrão 3 h) a Session é nova e o anterior só chega pelo Summary e pela History Search. O resto está no Summary ou na History Search ([agent.md](agent.md#memória)).
- **O Summary não atualiza**: procure `Summary refresh failed` ou `Falha ao atualizar o Summary` no worker. Falha aqui nunca bloqueia a resposta; o próximo Turn tenta de novo. Ele roda quando a janela da Session atual passa de `MEMORY_WINDOW` (20) Messages, ou quando há 20 Messages de Sessions anteriores ainda não resumidas.
- **`buscar_historico` volta vazio em dev**: em SQLite (testes) a busca é por `ILIKE` de todas as palavras; em Postgres é full-text em português.
