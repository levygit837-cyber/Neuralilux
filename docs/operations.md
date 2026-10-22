# Operação: Handoff, Tickets e troubleshooting

Termos conforme o [glossário](../CONTEXT.md). Setup inicial em [setup.md](setup.md); o caminho de uma Message em [architecture.md](architecture.md).

## Handoff e Tickets

Handoff é a passagem da Conversation do Agent para um Attendant. Enquanto vale, o Agent não responde. O estado mora em `Conversation`: `human_in_loop`, `human_handoff_reason`, `ticket_id` e `assigned_agent_id`.

### Como o Handoff começa

- **Pelo Agent.** O modelo chama `transferir_atendente(motivo)`. A Tool abre um Ticket (`status=open`, `reason`, `content` com a última Message do Contact), liga `human_in_loop`, grava `human_handoff_reason` e `ticket_id`, encerra o Turn com uma mensagem fixa ao Contact e publica `human_handoff_requested`. Se a Conversation já está em Handoff com Ticket, não abre outro.
- **Por um Attendant.** `POST /api/v1/conversations/{id}/take-control` (corpo opcional `{"reason": "..."}`) liga `human_in_loop` e grava `assigned_agent_id` com o usuário. **Não cria Ticket.**

O gate é lido do banco a cada Turn e de novo antes de enviar a resposta: se um Attendant assume enquanto o modelo ainda está respondendo, a resposta do Agent é descartada.

### Atender

1. Veja os Handoffs abertos: `GET /api/v1/tickets?status=open`. O evento `human_handoff_requested` chega ao Socket.IO, mas o dashboard atual ainda não o consome; um painel externo pode assiná-lo.
2. Atribua o Ticket: `POST /api/v1/tickets/{id}/assign?user_id=<usuário>` (vai para `in_progress`).
3. Responda pelo dashboard ou por `POST /api/v1/conversations/{id}/messages` (a Instance precisa estar `connected`).
4. Feche o Ticket: `PATCH /api/v1/tickets/{id}?status=closed`.
5. **Devolva a Conversation ao Agent:** `POST /api/v1/conversations/{id}/release-control`.

Fechar o Ticket **não** devolve a Conversation ao Agent, e `release-control` **não** fecha o Ticket. São dois passos. Esquecer o 5 deixa o Contact sem resposta automática.

### Ticket

| Campo | Significado |
|---|---|
| `status` | `open`, `in_progress` ou `closed`. Outro valor devolve 400. |
| `reason` | Motivo informado pelo Agent. |
| `content` | Última Message do Contact antes do Handoff. |
| `assigned_to` | Usuário (Attendant) responsável. |
| `agent_type` | Sempre `whatsapp_agent` hoje; o filtro por `sales`/`sac` é resto do desenho antigo. |

`GET /tickets` aceita `status`, `agent_type`, `assigned_to`, `skip` e `limit` (máx. 100) e lista só os Tickets das Instances do usuário (superusuário: todos). `GET`, `PATCH` e `assign` de um Ticket de outra Instance respondem 404. `assign` (e `PATCH ?assigned_to=`) só aceita um usuário da mesma Company da Instance do Ticket; numa Instance sem Company, só o superusuário atribui. `GET /conversations/{id}/human-control-status` mostra o estado atual da Conversation.

### Limites conhecidos

- Não há Handoff automático quando um Attendant escreve pelo celular; só `take-control` ou a Tool ligam o estado.
- `PATCH /tickets/{id}` recebe `status` e `assigned_to` como query string, não JSON.

## Troubleshooting

Os logs são estruturados (`structlog`). API e worker são processos separados: procure no log certo.

### O Agent não responde

Siga a ordem; o primeiro que bater é a causa. Mensagens em `código` aparecem no log do **worker**.

| Sintoma no log | Causa | Correção |
|---|---|---|
| Nada: nenhuma linha `Processing webhook event` | O webhook não chega à fila ou o worker está parado. | Veja as duas linhas abaixo. |
| `Message for unknown instance discarded` | Não há Instance com `evolution_instance_id` igual ao nome na Evolution. | Crie a Instance por `POST /api/v1/instances/{nome}` (é a única rota que grava a linha local) e tente de novo. |
| `Group or broadcast message ignored` | Chat de grupo (`@g.us`) ou lista de transmissão (`@broadcast`). A Message é descartada antes de ser gravada. | Esperado: o Agent não atende grupos nem listas. Nada fica no banco. |
| `Message not processed by agent` com `reason=from_me` | Mensagem enviada pelo próprio número. | Esperado. |
| `reason=unresolved_lid` | JID `@lid` sem número real: não há como responder. | Esperado; aguarde o Contact aparecer com número. |
| `reason=stale` | Mensagem mais velha que 5 min em relação ao início do worker (backlog de uma queda). | Esperado; fica gravada, sem resposta. |
| `Agent disabled for this instance` | `agent_enabled=false` na Instance. | `PATCH /instances/{nome}/agent-status` com `{"agent_enabled": true}`. |
| `No active Agent for this Instance or its Company` | A Company não tem Agent ativo. | `python scripts/seed_data.py` (cria um por Company e liga as Instances). Aparece uma vez por Instance até o worker reiniciar. |
| `Instance has no Company, Agent cannot run` | `instances.company_id` nulo: Instance criada antes de a API gravar a Company. | Um superusuário com Company chama `POST /api/v1/instances/{nome}`: assume a Instance e grava a Company dele. Veja [setup.md](setup.md#ligar-a-instance-à-company-e-ao-agent). |
| `Conversation in Handoff, Agent stays silent` | A Conversation está em Handoff. | Atenda e chame `release-control` (veja acima). |
| `Turn failed` e o Contact recebe "Desculpe, tive um problema…" | Exceção dentro do Turn; o stack trace vem logo antes. | Causas comuns abaixo. |
| `Unexpected error processing message with agent` com `EvolutionAPIError` logo depois de `Turn finished` | O Turn rodou, mas o envio pela Evolution falhou: Instance não conectada ao WhatsApp, Evolution fora do ar ou `EVOLUTION_API_URL`/`EVOLUTION_API_KEY` errados. A Message do Contact fica gravada; a resposta não. | Conecte a Instance (QR code) e confira `GET {EVOLUTION_API_URL}/instance/fetchInstances` com o header `apikey`. |

Causas comuns de `Turn failed`:

- `LLMNotConfiguredError: Nenhum Gateway atribuido…`: nenhum modelo atribuído a `whatsapp_agent` nem a `default`. Atribua em **Configurações > Gateways**.
- `LLMNotConfiguredError` com a chave do Gateway: a chave não abre. `SECRET_KEY` mudou, ou o banco tem chaves de antes do HKDF; rode `python scripts/reencrypt_gateway_secrets.py` (a primeira vem de [setup.md](setup.md)) ou regrave a chave do Gateway.
- `LLMProviderError`: o Gateway respondeu fora do formato, deu 5xx ou estourou o timeout (60 s por padrão, 3 tentativas). Teste com `POST /gateways/models/{id}/test`.
- Gateway em `localhost` com a API em container: dentro do container use `http://host.docker.internal:<porta>`.

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
- O socket exige o JWT em `auth.token`; sem ele a conexão é recusada. O cliente precisa chamar `subscribe_instance` e `join_conversation`.
- Há polling de contingência no frontend para mensagens, mas não para esses eventos.

### A app não sobe

- `SECRET_KEY de exemplo nao pode ser usada…` ou `EVOLUTION_WEBHOOK_TOKEN vazio ou de exemplo…`: com `ENVIRONMENT != development` os valores de exemplo são recusados. Defina valores fortes.
- Erro de migração com mais de uma head: veja [agents/migrations.md](agents/migrations.md).
- O worker sai com `Failed to connect to RabbitMQ`: confira `RABBITMQ_URL`, o vhost `neuralilux` e `docker compose --env-file backend/.env ps`.

### Memória

- **O Agent esqueceu algo antigo**: só a Recent Window (20 Messages) entra literal. O resto está no Summary ou na History Search ([agent.md](agent.md#memória)).
- **O Summary não atualiza**: procure `Summary refresh failed` ou `Falha ao atualizar o Summary` no worker. Falha aqui nunca bloqueia a resposta; o próximo Turn tenta de novo. Só roda após 20 Messages fora da janela ainda não resumidas.
- **`buscar_historico` volta vazio em dev**: em SQLite (testes) a busca é por `ILIKE` de todas as palavras; em Postgres é full-text em português.
