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
- **Eco do aviso**: o eco `fromMe` do aviso nunca é atividade de Attendant (não reinicia o timeout do Handoff, #35) nem uma segunda Message. Com id da Evolution, o dedup por `message_id` basta. Sem id, o aviso fica gravado com `message_id` NULL e o consumer reconhece o eco no banco (`whatsapp/system_notice.adopt_echo`: Conversation + texto + janela de 2 min) e grava o id nele. Vale entre processos (API grava, worker consome).
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
| `Unexpected error processing message with agent` com `EvolutionAPIError` logo depois de `Turn finished` | O Turn rodou, mas o envio pela Evolution falhou: Instance não conectada ao WhatsApp, Evolution fora do ar ou `EVOLUTION_API_URL`/`EVOLUTION_API_KEY` errados. A Message do Contact fica gravada; a resposta não. | Conecte a Instance (QR code) e confira `GET {EVOLUTION_API_URL}/instance/fetchInstances` com o header `apikey`. |

Causas comuns de `Turn failed`:

- `LLMNotConfiguredError: Nenhum Gateway atribuido…`: nenhum modelo atribuído a `whatsapp_agent` nem a `default`. Atribua em **Configurações > Gateways**.
- `LLMNotConfiguredError` com a chave do Gateway: a chave não abre. A `GATEWAY_ENCRYPTION_KEY` mudou, ou o banco ainda tem chaves criptografadas com a `SECRET_KEY` (antes da chave própria); rode `python scripts/reencrypt_gateway_secrets.py` (passo único, veja [Atualizar um banco existente](#atualizar-um-banco-existente-chaves-de-gateway)) ou regrave a chave do Gateway.
- `LLMProviderError`: o Gateway respondeu fora do formato, deu 5xx ou estourou o timeout (60 s por padrão, 3 tentativas). Teste com `POST /gateways/models/{id}/test`.
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

### O webhook não chega à fila

- **401 no webhook**: o token da URL não bate com `EVOLUTION_WEBHOOK_TOKEN` do `backend/.env`, ou a variável está vazia ([ADR 0006](adr/0006-webhook-token-auth.md)). Confira `WEBHOOK_GLOBAL_URL` no serviço `evolution-api` e se o compose foi subido com `--env-file backend/.env`.
- **Token chega como `TOKEN/messages-upsert`**: o serviço da Evolution está com `WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=true`. Ponha `false` (motivo em [setup.md](setup.md#2-infra-postgresql-redis-rabbitmq-evolution)).
- **A Evolution não alcança a API**: no Linux o container precisa de `extra_hosts: host.docker.internal:host-gateway` e a API de `--host 0.0.0.0`.
- **A fila cresce e nada consome**: o worker não está rodando (`python scripts/run_worker.py`). Veja a fila `webhooks.evolution` no painel do RabbitMQ (`http://localhost:15672`, vhost `neuralilux`, usuário e senha de dev do compose). A fila guarda até 24 h e 100 mil Messages.
- Uma Message cujo processamento falha volta à fila **uma vez**; se falhar de novo, é descartada e logada em `error` (`Processing error, requeueing once`). JSON inválido é descartado sem requeue.

### Instance e QR code

- **QR code não aparece**: confirme `CONFIG_SESSION_PHONE_VERSION` no serviço da Evolution e o limite de tentativas (`QRCODE_LIMIT=30`); reinicie a Instance (`DELETE /instances/{nome}/logout`, depois `POST /instances/{nome}/connect`).
- **`POST /instances/{nome}/connect` devolve `qr_code: null` e "already open"**: a Instance já está conectada; não há QR.
- **O status da Instance não atualiza**: o evento `connection.update` depende do webhook; veja a seção anterior.

### Dashboard sem eventos ao vivo

- `thinking_event`, `tool_event` e `human_handoff_requested` saem do **worker** pelo Redis: API e worker precisam usar o mesmo `REDIS_URL`. O dashboard atual só consome `thinking_event`; os outros dois estão disponíveis no Socket.IO para quem os assinar.
- **Redis lento ou fora**: o evento de UI nunca segura o Turn além de `REALTIME_PUBLISH_TIMEOUT_SECONDS` (1 s; o fechamento do cliente descartado roda em background) nem o derruba; o evento é perdido e logado (`Realtime event dropped`). Depois de uma falha, os eventos seguintes são descartados por `REALTIME_PUBLISH_COOLDOWN_SECONDS` (5 s) e o cliente reconecta do zero. O cooldown precisa ser maior que o teto: a app recusa subir se não for. O cliente usa `REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS`, `REDIS_SOCKET_TIMEOUT_SECONDS` e `REDIS_HEALTH_CHECK_INTERVAL_SECONDS`.
- **503 no webhook / `Evolution webhook event lost` no log**: o RabbitMQ recusou o publish. A Evolution reenvia o webhook (até 10 vezes, backoff até 300 s; detalhes em [evolution-data-formats.md](agents/evolution-data-formats.md)); o caminho websocket não reenvia.
- O socket exige o JWT em `auth.token`; sem ele, com token inválido/vencido ou de usuário inativo a conexão é recusada (mesma regra da API HTTP). O cliente precisa chamar `subscribe_instance` e `join_conversation`. Desativar o usuário recusa conexões novas e os eventos `subscribe_instance`, `join_conversation` e `send_message`, mas um socket já aberto segue recebendo os `emit` da sala até desconectar.
- Há polling de contingência no frontend para mensagens, mas não para esses eventos.

### A app não sobe

- `Configuração recusada com ENVIRONMENT='production' (sem ENVIRONMENT definido vale 'production')…`: sem `ENVIRONMENT=development` explícito a app recusa `SECRET_KEY`, `EVOLUTION_WEBHOOK_TOKEN` e `GATEWAY_ENCRYPTION_KEY` vazios ou de exemplo (e exige `GATEWAY_ENCRYPTION_KEY` diferente da `SECRET_KEY`, as duas com 32+ caracteres). Em dev local, ponha `ENVIRONMENT=development` no `backend/.env`. Fora dele, defina valores fortes e distintos (`python3 -c "import secrets; print(secrets.token_urlsafe(48))"`).
- Erro de migração com mais de uma head: veja [agents/migrations.md](agents/migrations.md).
- O worker sai com `Failed to connect to RabbitMQ`: confira `RABBITMQ_URL`, o vhost `neuralilux` e `docker compose --env-file backend/.env ps`.

### Atualizar um banco existente: chaves de Gateway

Passo único e obrigatório ao atualizar um banco que já tem Gateways com chave de API, **antes de subir a app**:

1. Backup: `pg_dump -t inference_gateways "$DATABASE_URL" > inference_gateways.sql` (URL `postgresql://…`, sem o `+psycopg`). O script regrava os tokens e não tem volta.
2. No `backend/.env`, defina `GATEWAY_ENCRYPTION_KEY` (valor **real**, com 32+ caracteres e diferente da `SECRET_KEY`) e mantenha a `SECRET_KEY` atual. Com a chave vazia ou de exemplo o script recusa rodar (exit 1) e não altera nada, mesmo em `development`.
3. `cd backend && python scripts/reencrypt_gateway_secrets.py`. Imprime quantas chaves converteu.

O script abre cada chave com a `SECRET_KEY` (HKDF ou SHA-256 antigo) e regrava com a `GATEWAY_ENCRYPTION_KEY`. Idempotente: a segunda execução imprime 0 e não altera nada. Chaves que nenhuma das duas abre ficam intactas (regrave-as pela API). Depois disso a `SECRET_KEY` pode ser rotacionada sem tocar nos Gateways; já trocar a `GATEWAY_ENCRYPTION_KEY` invalida as chaves salvas. Só o script re-criptografa; seed, API e worker nunca mexem nos tokens.

### Agrupamento e prefetch

A Message que abre uma rajada (a líder) segura a entrega do RabbitMQ durante a janela (`DEBOUNCE_SECONDS`, padrão 3 s) e todos os Turns da rajada, que levam segundos com o modelo. As seguidoras voltam logo depois de gravadas. Cada líder ocupa, portanto, um slot do `RABBITMQ_PREFETCH` (padrão 8) por esse tempo.

- **Teto.** No máximo `RABBITMQ_PREFETCH` Conversations em rajada ao mesmo tempo por worker. Com todos os slots ocupados por líderes, as Messages seguintes de qualquer Conversation esperam na fila até um Turn terminar: o Contact vê atraso, não perda.
- **Dimensionar.** `RABBITMQ_PREFETCH` deve ser no mínimo o número de Conversations que você espera ver em atendimento ao mesmo tempo por worker, mais uma folga para as seguidoras (cada uma ocupa um slot só até ser gravada). O pool do banco (`pool_size=10`, `max_overflow=20` em `app/core/database.py`) precisa acompanhar: a líder devolve a conexão do consumer antes de esperar a janela, mas o Turn abre a própria Session e a segura até a resposta sair.
- **Desligar.** `DEBOUNCE_SECONDS=0` volta a um Turn por Message e libera o slot assim que o Turn termina.
- **Sintoma de prefetch curto.** Resposta atrasada com o worker ocioso e Messages prontas na fila `webhooks.evolution`: suba `RABBITMQ_PREFETCH` e reinicie o worker.

### Memória

- **O Agent esqueceu algo antigo**: só a Recent Window (cerca de 11 a 22 Messages da Session atual, cortada em blocos de `MEMORY_WINDOW_BLOCK`) entra literal; depois de uma pausa maior que `session_timeout_minutes` da Company (padrão 3 h) a Session é nova e o anterior só chega pelo Summary e pela History Search. O resto está no Summary ou na History Search ([agent.md](agent.md#memória)).
- **O Summary não atualiza**: procure `Summary refresh failed` ou `Falha ao atualizar o Summary` no worker. Falha aqui nunca bloqueia a resposta; o próximo Turn tenta de novo. Ele roda quando a janela da Session atual passa de `MEMORY_WINDOW` (20) Messages, ou quando há 20 Messages de Sessions anteriores ainda não resumidas.
- **`buscar_historico` volta vazio em dev**: em SQLite (testes) a busca é por `ILIKE` de todas as palavras; em Postgres é full-text em português.
