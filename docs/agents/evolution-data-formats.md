# Formatos de dados da Evolution API

O que a Evolution `v2.3.7` (`evoapicloud/evolution-api:v2.3.7`) devolve e envia, medido numa instância real de dev (WhatsApp Baileys, `syncFullHistory: true`, 3353 Messages, 12 chats, 2020 contatos, 6 grupos). Serve de referência para quem mexe em `backend/app/whatsapp/` (`webhook_parser.py`, `evolution_history.py`, `history_sync.py`, `status_events.py`, `consumer.py`).

## Como isto foi levantado

- **Somente leitura.** Só `POST /chat/find*`, `GET /group/fetchAllGroups`, `GET /settings/find` e `GET /instance/connectionState`, mais leitura do código e do ambiente do container. Nenhuma mensagem enviada, nenhum webhook ou instância alterado.
- **Anonimização.** Todo exemplo abaixo foi reconstruído a partir do formato real: números, JIDs, nomes, textos, ids, URLs e chaves de mídia são fictícios (`5511999990001`, `100000000000001@lid`, `120363000000000001@g.us`). Os formatos (campos, tipos, contagens) são os reais.
- **Níveis de evidência**, marcados em cada seção:
  - **[medido]**: visto numa resposta real da instância.
  - **[fonte]**: lido no código da imagem rodando (`/evolution/dist/main.js`) ou no banco da Evolution (só nomes de colunas e contagens).
  - **[não exercitado]**: exigiria escrever na Evolution (envio); vem do nosso código e do código da Evolution, sem resposta real.

## Endpoints de leitura

Todos usam o header `apikey: <EVOLUTION_API_KEY>`. O backend chama via `evolution_history.py` (timeout 60 s).

### `POST /chat/findChats/{instance}` [medido]

Corpo `{}` (obrigatório na v2.3.7; um GET não existe). Devolve **lista pura**, um item por chat: 12 itens (5 `@lid`, 4 `@s.whatsapp.net`, 3 `@g.us`).

```json
{
  "id": "cm0000000000000000000000a",
  "remoteJid": "100000000000001@lid",
  "pushName": null,
  "profilePicUrl": "https://example.invalid/pp.jpg",
  "updatedAt": "2026-01-01T12:00:00.000Z",
  "windowStart": null,
  "windowExpires": null,
  "windowActive": false,
  "lastMessage": {
    "id": "cm0000000000000000000000b",
    "key": { "id": "3EB0AAAAAAAAAAAAAAAA", "fromMe": false, "remoteJid": "100000000000001@lid" },
    "pushName": "Pessoa Exemplo",
    "participant": null,
    "messageType": "conversation",
    "message": { "conversation": "texto de exemplo" },
    "source": "ios",
    "messageTimestamp": 1790000000,
    "instanceId": "00000000-0000-0000-0000-000000000000",
    "sessionId": null,
    "status": "DELIVERY_ACK"
  },
  "unreadCount": null,
  "isSaved": false
}
```

- `id` é um id interno (cuid), **não** o JID. O JID é `remoteJid`.
- `unreadCount` é `null` em 7 dos 12 chats e inteiro nos outros 5. `history_sync._apply_unread` já ignora `null`.
- `pushName` só veio preenchido em 4 de 12 chats. O nome de exibição vem de outras fontes (veja "Nome de exibição").
- `lastMessage` sempre presente (12/12), no formato de um record do `findMessages` sem `MessageUpdate`; `status` ∈ `PENDING`, `DELIVERY_ACK`, `READ`.
- Chat de grupo traz `lastMessage.key.participant` (e `participantAlt`/`addressingMode`, veja "Identidades").
- 4 dos 5 chats `@lid` têm o número real em algum `remoteJidAlt` do histórico; 1 não tem.

### `POST /chat/findContacts/{instance}` [medido]

Corpo `{}`. Lista pura, 2020 itens: 2000 em `@lid` (1997 `contact` + 3 `group_member`), 14 em `@s.whatsapp.net`, 6 grupos (`type: "group"`, `isGroup: true`).

```json
{
  "id": "cm0000000000000000000000c",
  "remoteJid": "100000000000002@lid",
  "pushName": "Pessoa Exemplo",
  "profilePicUrl": null,
  "createdAt": "2026-01-01T12:00:00.000Z",
  "updatedAt": "2026-01-01T12:00:00.000Z",
  "instanceId": "00000000-0000-0000-0000-000000000000",
  "isGroup": false,
  "isSaved": false,
  "type": "contact"
}
```

- `pushName` vazio em 10 itens; `profilePicUrl` `null` em 1769 (87%).
- **Não há `remoteJidAlt` no contato**: o `findContacts` não resolve `@lid` para número. Esse par só aparece em `key.remoteJidAlt` das Messages.

### `GET /group/fetchAllGroups/{instance}?getParticipants=false` [medido]

Lista pura, 6 grupos. Sem `participants` (com `getParticipants=true` a Evolution devolve a lista, o backend não usa).

```json
{
  "id": "120363000000000001@g.us",
  "subject": "Grupo Exemplo",
  "subjectOwner": "100000000000003@lid",
  "subjectTime": 1790000000,
  "pictureUrl": null,
  "size": 12,
  "creation": 1780000000,
  "owner": "100000000000003@lid",
  "desc": "descrição de exemplo",
  "descId": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
  "restrict": false,
  "announce": false,
  "isCommunity": false,
  "isCommunityAnnounce": false
}
```

- `subjectOwner`, `desc`, `descId`, `owner` são opcionais (ausentes em 1 a 2 dos 6 grupos). Só `id`, `subject`, `subjectTime`, `size`, `creation`, `restrict`, `announce`, `isCommunity`, `isCommunityAnnounce` e `pictureUrl` vieram sempre.
- Os 3 grupos de `findChats` estão aqui; os outros 3 são grupos sem chat.

### `POST /chat/findMessages/{instance}` [medido]

Corpo `{ "page": 1, "offset": 500 }`. Resposta:

```json
{ "messages": { "total": 3353, "pages": 7, "currentPage": 1, "records": [ "..." ] } }
```

Comportamento verificado:

| Pedido | Resultado |
|---|---|
| `{page: 1, offset: 5}` | `pages: 671` (= ceil(total/offset)), 5 records |
| `{page: 2, offset: 5}` | records diferentes dos da página 1 (sem sobreposição) |
| `{page: 99, offset: 500}` | `records: []`, `currentPage: 99` (não dá erro) |
| `{page: 0, offset: 5}` | tratado como página 1 |
| `{}` | `offset` default 50, `pages: 68` |
| `{page: 1, offset: 5000}` | 1 página com os 3353 records |
| `{where: {key: {remoteJid: "<jid>"}}, page: 1, offset: 500}` | filtra por chat; `total` bate com a contagem local |

- **Ordem: da mais nova para a mais antiga.** Conferido nos 3353 records (`messageTimestamp` estritamente não crescente entre páginas). O backend usa `MESSAGES_PAGE_SIZE = 500` e `pages`.
- `messageTimestamp` é inteiro em segundos (UTC) em todos os records.
- `record.id` é id interno (cuid); o id do WhatsApp, usado em `Message.message_id`, é `record.key.id`.
- `contextInfo` é `null` em 2245 records e objeto nos demais.
- `MessageUpdate` é lista de `{ "status": ... }`, vazia em 3327 records e com 2 a 5 itens em 26; **a ordem não é cronológica** (ex.: `DELIVERY_ACK`, `READ`, `SERVER_ACK`). Valores vistos: `SERVER_ACK`, `DELIVERY_ACK`, `READ`.
- `source` ∈ `ios` (1321), `android` (1302), `unknown` (545), `web` (185). `web` são as 26 Messages 1:1 enviadas pela API (todas `fromMe`, em `@s.whatsapp.net`).

#### Record base

```json
{
  "id": "cm0000000000000000000000d",
  "key": {
    "id": "3EB0AAAAAAAAAAAAAAAA",
    "fromMe": false,
    "remoteJid": "120363000000000001@g.us",
    "participant": "100000000000004@lid",
    "participantAlt": "5511999990004@s.whatsapp.net",
    "addressingMode": "lid"
  },
  "pushName": "Pessoa Exemplo",
  "messageType": "conversation",
  "message": { "conversation": "texto de exemplo", "messageContextInfo": { "threadId": [], "messageSecret": "AAAA" } },
  "messageTimestamp": 1790000000,
  "instanceId": "00000000-0000-0000-0000-000000000000",
  "source": "ios",
  "contextInfo": null,
  "MessageUpdate": []
}
```

Campos de `key` (contagem nos 3353 records): `id`, `fromMe`, `remoteJid` (sempre); `participant` (3295); `addressingMode` (146); `participantAlt` (120); `remoteJidAlt` (26).

## Identidades: `@lid`, `remoteJidAlt`, `participant` [medido]

Em todos os 3353 records, `remoteJid` termina em: `@g.us` (3270), `@lid` (57), `@s.whatsapp.net` (26).

- **1:1 recebido chega como `@lid`.** Os 26 records em `@s.whatsapp.net` são todos `fromMe` (enviados pela API, `source: "web"`). O JID de telefone aparece no recebido só como `key.remoteJidAlt`.
- **`remoteJidAlt`** (26 de 57 records `@lid`): sempre `...@s.whatsapp.net`, junto de `addressingMode: "lid"` e `participant: ""` (string vazia, não ausente).

  ```json
  { "id": "3EB0AAAAAAAAAAAAAAAA", "fromMe": false, "remoteJid": "100000000000001@lid",
    "remoteJidAlt": "5511999990001@s.whatsapp.net", "participant": "", "addressingMode": "lid" }
  ```
- **31 dos 57 records `@lid` não trazem `remoteJidAlt`**: 27 `imageMessage` e 2 `audioMessage` recebidos, e 2 `conversation` `fromMe`. Ou seja, o par `@lid`↔número aparece em uma parte das Messages do mesmo chat; `history_sync._lid_aliases(records)` junta os pares de todo o histórico por isso. Mídia recebida de um `@lid` sozinha não resolve o número.
- **Grupo**: `key.participant` é o autor e **sempre termina em `@lid`** (3269 de 3270). Falta só num `protocolMessage` `fromMe` do próprio número. Em 120 records o par `participantAlt` (`@s.whatsapp.net`) acompanha `addressingMode: "lid"`.
- `remoteJid` de grupo vem em dois formatos: `120363...@g.us` (18 dígitos, 2689 records) e `<dígitos>-<dígitos>@g.us` (formato antigo, 581 records).
- No `findContacts`, `owner`/`subjectOwner` do `fetchAllGroups` também vêm como `@lid`.

Como o código trata: `resolve_remote_jid` troca um `@lid` por `remoteJidAlt` (ou `senderPn`) quando vier, senão deixa o `@lid`; o consumer grava a Conversation mas o Agent pula (`unresolved_lid`). Grupo é gravado e o Agent nunca fala (`group`).

## Tipos de mensagem e o parser [medido]

Contagem por `messageType` nos 3353 records, e o que `webhook_parser.py` faz (o parser olha as **chaves de `message`**, não o `messageType`):

| `messageType` | Qtd | Chaves em `message` | Tratamento |
|---|---|---|---|
| `conversation` | 2332 | `conversation` (+ `messageContextInfo`, às vezes `senderKeyDistributionMessage`) | `text`; visível |
| `stickerMessage` | 488 | `stickerMessage` (`image/webp`) | `sticker`, `[Sticker]`; mídia |
| `imageMessage` | 418 | `imageMessage` (`image/jpeg`, 107 com `caption`) | `image`, legenda ou `[Imagem]`; mídia |
| `videoMessage` | 40 | `videoMessage` (`video/mp4`, 29 com `caption`) | `video`, legenda ou `[Vídeo]`; mídia |
| `audioMessage` | 30 | `audioMessage` (`ptt` em 27; `audio/ogg; codecs=opus` e `audio/mpeg`) | `audio`, `[Áudio]`; mídia |
| `associatedChildMessage` | 39 | `associatedChildMessage.message.imageMessage` + `messageContextInfo.messageAssociation` | desembrulhado como `imageMessage` (foto do álbum) |
| `albumMessage` | 1 | `albumMessage` | invisível (cabeçalho do álbum) |
| `reactionMessage` | 1 | `reactionMessage` | invisível |
| `protocolMessage` | 3 | `protocolMessage` | invisível |
| `unknown` | 1 | só `messageContextInfo` + `senderKeyDistributionMessage` | invisível |

Não apareceu nenhum `extendedTextMessage`, `ephemeralMessage`, `viewOnce*`, `documentMessage`, `pollUpdateMessage` ou `editedMessage` de topo nesta instância; o parser os trata por precaução (texto estendido e `documentMessage` como mídia/texto, embrulhos desembrulhados, o resto invisível), sem exemplo real aqui.

### Álbum

Cada foto do álbum é um record próprio com `messageType: "associatedChildMessage"`:

```json
{
  "key": { "id": "3EB0AAAAAAAAAAAAAAAA", "fromMe": false, "remoteJid": "120363000000000001@g.us", "participant": "100000000000004@lid" },
  "messageType": "associatedChildMessage",
  "message": {
    "messageContextInfo": {
      "threadId": [],
      "messageSecret": "AAAA",
      "messageAssociation": {
        "associationType": 10,
        "parentMessageKey": { "id": "3EB0BBBBBBBBBBBBBBBB", "fromMe": false, "remoteJid": "120363000000000001@g.us", "participant": "100000000000004@lid" }
      }
    },
    "associatedChildMessage": {
      "message": { "imageMessage": { "mimetype": "image/jpeg", "width": 1280, "height": 960, "fileLength": { "low": 331869, "high": 0, "unsigned": true } } }
    }
  }
}
```

- `associationType` é sempre `10` (39 de 39); o `imageMessage` interno nunca traz `caption` nesta amostra.
- O `parentMessageKey.id` de cada filho aponta para um record `imageMessage` comum do mesmo `remoteJid` (39 de 39, 39 pais distintos; nenhum aponta para o filho ou para o `albumMessage`). Cada foto vira uma Message de mídia; o parser não reagrupa o álbum.
- O cabeçalho (`albumMessage`) veio uma vez, com `{ "expectedImageCount": 0, "expectedVideoCount": 0 }`, e nenhum filho aponta para ele.

### Reação, protocolo, edição

```json
{ "reactionMessage": { "key": { "id": "3EB0CCCCCCCCCCCCCCCC", "fromMe": false, "remoteJid": "120363000000000001@g.us", "participant": "100000000000004@lid" },
    "text": "👍", "senderTimestampMs": { "low": 1, "high": 0, "unsigned": false } } }
```

`protocolMessage` visto com 2 formas (3 records, todos em grupo):

- `type: 30` com `memberLabel: { label, labelTimestamp }` (`fromMe`; sem `participant` na key).
- `type: 14` (edição): `{ key, type: 14, timestampMs, editedMessage: { imageMessage: { caption, ... } } }`. **A edição chega como um record novo; a Message original não é alterada pelo parser.**

## Envio e presença [não exercitado]

Não foi enviado nada. O contrato vem de `evolution_client.py` e do código da Evolution.

- `POST /message/sendText/{instance}`, corpo `{ "number": <alvo>, "text": "...", "options": { "delay": 1200, "presence": "composing" } }`. Sucesso esperado: objeto com `key.id` (o `send_text_message` valida isso).
- `POST /chat/sendPresence/{instance}`, corpo `{ "number": <alvo>, "presence": "composing", "delay": <ms> }`. A Evolution só responde depois do `delay`; por isso o cliente usa timeout curto e trata `ReadTimeout` como aceito.
- `<alvo>` (`_recipient`): contato 1:1 vai só com os dígitos (`5511999990001`); grupo (`@g.us`) e `@lid` vão com o JID inteiro. A função de normalização da Evolution (`G(...)` no dist) deixa passar sem alterar qualquer valor que contenha `@g.us`, `@s.whatsapp.net`, `@lid` ou `@broadcast`, e para números sem `@` remove não dígitos e acrescenta `@s.whatsapp.net` (ou `@g.us` se parecer id de grupo). Isso confirma por leitura de código que `@lid` e grupo com JID inteiro são aceitos; **a entrega real a `@lid` e a grupo não foi testada aqui**.
- `sendPresence` na Evolution verifica `whatsappNumber` antes de enviar e falha se o número não existir (exceto grupo e broadcast).

## Webhook: eventos e configuração

### Como a Evolution decide o que entra no webhook global [fonte]

No `WebhookController.emit` do dist, o webhook **global** dispara quando `WEBHOOK_GLOBAL_ENABLED=true` **e** `WEBHOOK_EVENTS_<EVENTO>=true` (evento em maiúsculas, `.` e `-` viram `_`). Não há outra lista: o que não está `true` não chega.

- Container `neuralilux-evolution` (imagem `v2.3.7`): `WEBHOOK_GLOBAL_ENABLED=true`, `WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false`, `WEBHOOK_GLOBAL_URL=http://host.docker.internal:8000/api/v1/webhooks/evolution?token=<redigido>`. **Nenhuma variável `WEBHOOK_EVENTS_*` está no ambiente do container** (o compose atual não define).
- Sem elas, valem os defaults do arquivo `/evolution/.env` da imagem (`dotenv`), que deixa `true`: `QRCODE_UPDATED`, `MESSAGES_SET/UPSERT/EDITED/UPDATE/DELETE`, `SEND_MESSAGE(_UPDATE)`, `CONTACTS_SET/UPSERT/UPDATE`, `PRESENCE_UPDATE`, `CHATS_SET/UPSERT/UPDATE/DELETE`, `GROUPS_UPSERT/UPDATE`, `GROUP_PARTICIPANTS_UPDATE`, `CONNECTION_UPDATE`, `LABELS_EDIT/ASSOCIATION`, `CALL`; e `false`: `APPLICATION_STARTUP`, `REMOVE_INSTANCE`, `LOGOUT_INSTANCE`, `ERRORS`. Ou seja, **hoje o webhook recebe quase tudo**, inclusive eventos que o consumer não usa.
- `WEBHOOK_REQUEST_TIMEOUT_MS=60000`, retry até 10 tentativas com backoff exponencial (5 s a 300 s). Status 400, 401, 403, 404, 422 não são repetidos.

### Resposta não-2xx: a Evolution reenvia? [fonte]

Sim, no webhook HTTP. Lido em `WebhookController.retryWebhookRequest` da tag `2.3.7` ([webhook.controller.ts](https://github.com/EvolutionAPI/evolution-api/blob/2.3.7/src/api/integrations/event/webhook/webhook.controller.ts)), com os defaults de [`.env.example`](https://github.com/EvolutionAPI/evolution-api/blob/2.3.7/.env.example) (linhas `WEBHOOK_REQUEST_TIMEOUT_MS` e `WEBHOOK_RETRY_*`):

- Qualquer erro do `axios.post` (status fora de 2xx, timeout de `WEBHOOK_REQUEST_TIMEOUT_MS`, conexão recusada) entra no retry, **exceto** os status de `WEBHOOK_RETRY_NON_RETRYABLE_STATUS_CODES` (padrão `400,401,403,404,422`), que abortam na hora. Um **503 é reenviado**; o 401 do token errado não é.
- Até `WEBHOOK_RETRY_MAX_ATTEMPTS=10` tentativas, espera inicial de 5 s, dobrando a cada falha até 300 s, com jitter de ±20 %. No pior caso a Evolution insiste por mais de 20 minutos; esgotadas as tentativas, loga o erro e **descarta o evento**.
- O corpo reenviado é o mesmo envelope (`webhookData` é montado uma vez, antes do loop de retry; `date_time` não muda), e o reenvio chega fora de ordem e até ~20 min atrasado. O que o Neuralilux faz com isso, por evento:
  - `messages.upsert`: a Message já gravada é reconhecida por `message_id` e ignorada.
  - `messages.update`: o status só avança (`pending < failed < sent < delivered < read`; `ERROR` vira `failed`, `PLAYED` vira `read`). `READ` seguido de um `DELIVERY_ACK` reenviado continua `read`; o status velho é ignorado com log `debug` (`Stale message status ignored`). Se a Message ainda não existe (o ack chegou antes do `upsert`), loga `warning` (`Message status update for unknown message discarded`) e descarta: a Evolution não reenvia aquele ack.
  - `connection.update`: usa o `date_time` do envelope. Um evento com `date_time` anterior ao último aplicado para a Instance é ignorado (`debug`); igual ou posterior é aplicado. **Limites:** o último instante fica só na memória do processo do worker (persistir exigiria coluna nova e migração), então um reinício do worker o zera; e um evento sem `date_time` é aplicado como chega, sem proteção contra reordenação.
  - Demais eventos (`qrcode.updated` etc.): sem proteção; reaplicá-los é inofensivo (o QR mais novo vence só por ordem de chegada).
- **Não vale para o caminho do websocket** (`EvolutionRealtimeService`): o socket não tem ack nem retry. Se o publish no RabbitMQ falha ali, o evento só fica registrado no log (`Evolution realtime event lost`, com `event_type`, `instance` e `message_ids`) e se perde.
- Não conferi em runtime com o container: a conclusão vem do código da tag e dos defaults do `.env.example`; este ambiente não define nenhuma variável `WEBHOOK_RETRY_*`.

Por isso o webhook responde **503** quando o publish no RabbitMQ falha (`routes/webhooks.py`): a Evolution reenvia enquanto o broker volta. Sinal de alerta: o log `Evolution webhook event lost: publish to RabbitMQ failed` (ou `Evolution realtime event lost`). No webhook, ele repetido ao longo de minutos significa broker fora; se o broker não voltar em ~20 min, as Messages daquele período estão perdidas e só a History Sync recupera.

### Envelope [fonte, medido no websocket]

```json
{
  "event": "messages.upsert",
  "instance": "minha-instancia",
  "data": { "...": "..." },
  "destination": "<url do webhook>",
  "date_time": "2026-01-01T12:00:00.000-03:00",
  "sender": "5511999990009@s.whatsapp.net",
  "server_url": "http://localhost:8081",
  "apikey": null
}
```

Com `WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false` o nome vem em `event` e a URL não muda. O `apikey` veio `null` no envelope do websocket.

### Eventos e o que o consumer faz com eles

`data` por evento vem do código da Evolution (emissores no dist); `messages.upsert`, `messages.update` e `connection.update` se confirmam pelos dados reais deste doc (records e colunas). Os eventos marcados "dado" foram vistos no log do worker informado pelo solicitante e **não** reproduzidos por mim (veja "Limites da captura").

| Evento | `data` | Consumer (`consumer.process_webhook_event`) |
|---|---|---|
| `messages.upsert` | um record como no `findMessages`, sem `MessageUpdate` (`key`, `pushName`, `message`, `messageType`, `messageTimestamp`, `source`, `instanceId`) | `_save_message_to_database` |
| `messages.update` | **plano**: `{ messageId, keyId, remoteJid, fromMe, participant, status, instanceId }` (`status` ∈ `SERVER_ACK`, `DELIVERY_ACK`, `READ`); `keyId` é o `Message.message_id` | `update_message_status` |
| `connection.update` | `{ instance, state, statusReason, wuid, profileName, profilePictureUrl }` | `update_connection_status`; `state: "open"` dispara a importação de histórico |
| `qrcode.updated` | QR code e contador | `publish_qr_code_update` |
| `messages.set`, `chats.set`, `contacts.set` | histórico em lote | importação de histórico (`HISTORY_EVENTS`) |
| `chats.upsert` | **lista** `{ remoteJid, instanceId, name, unreadMessages }` | importação de histórico (`HISTORY_EVENTS`) |
| `contacts.update` | `{ remoteJid, pushName, instanceId }` | **não tratado**: cai em `Unknown webhook event` (warning) |
| `contacts.upsert`, `chats.update`, `chats.delete`, `messages.edited`, `messages.delete`, `send.message`, `presence.update`, `groups.upsert`, `groups.update`, `group.participants.update`, `labels.*`, `call` | vários | **não tratados** (warning `Unknown webhook event`) |

Evento que chegou ao websocket da Evolution durante a captura: `groups.update`, com `data` = lista de grupos (campos de `fetchAllGroups` mais `addressingMode`, `subjectOwnerPn`, `ownerPn`, `descOwner`, `descOwnerPn`, `descTime`, `joinApprovalMode`, `memberAddMode` e `participants: [{ id, phoneNumber, admin }]`).

### Limites da captura

- **Websocket global** (`WEBSOCKET_GLOBAL_EVENTS=true`): ouvi como cliente passivo por cerca de 7 minutos. Chegou só `groups.update` (1 evento). Sem mensagens novas na janela, não houve `messages.*`. O websocket global **não passa pelos `WEBHOOK_EVENTS_*`**: o `emit` do dist emite todo evento no canal global quando `GLOBAL_EVENTS` está ligado, sem filtro por evento.
- **Log do worker** (`scripts/run_worker.py`, rodando fora do Docker): o terminal dele não ficou legível para mim. A lista `contacts.update` (hoje sem tratamento), `messages.update`, `chats.upsert` e `messages.upsert` vem do solicitante, não de captura minha. A forma de `data` desses eventos está confirmada pelo código da Evolution e, para `messages.update`, também pelas colunas e contagens do banco da Evolution (`MessageUpdate`: `keyId`, `messageId`, `remoteJid`, `fromMe`, `participant`, `status`; 80 linhas).
- Os logs do container mostram falhas de entrega ao webhook global em dias anteriores (timeout de 60 s, status 500, `socket hang up`), com as tentativas de retry. **O log de erro imprime a `WEBHOOK_GLOBAL_URL` inteira, com o token na query string.** Trate `docker logs` da Evolution como sensível.

### Configuração mínima

Os eventos que o consumer usa e que `docker-compose.example.yml` agora liga explicitamente: `MESSAGES_UPSERT`, `MESSAGES_UPDATE`, `CONNECTION_UPDATE`, `QRCODE_UPDATED`, `MESSAGES_SET`, `CHATS_SET`, `CONTACTS_SET`, `CHATS_UPSERT`. O compose desliga os demais, para o webhook não gastar entrega com evento que cai em `Unknown webhook event`. Quem precisar de outro (por exemplo `contacts.update` para atualizar nomes) liga a variável e trata o evento no consumer.

O websocket (`evolution_realtime.py`) só encaminha 4 eventos (`messages.upsert`, `messages.update`, `connection.update`, `qrcode.updated`). O servidor emite todos no canal global, então desligar um `WEBHOOK_EVENTS_*` no compose **não** o tira do websocket; o cliente ignora o que não registrou.

## Nome de exibição

A ordem usada em `history_sync` é assunto do grupo, `pushName` de Message recebida, `findContacts`, `findChats`. Motivo medido: `findChats.pushName` vem vazio em 8 de 12 chats e `findContacts.pushName` em 10 de 2020, mas `pushName` dentro das Messages recebidas existe em 100% dos records. Em grupo, o `pushName` do record é o do autor, não o do grupo; em `fromMe` é o do nosso número.
