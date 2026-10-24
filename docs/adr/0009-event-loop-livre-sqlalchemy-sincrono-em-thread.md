# Event loop livre: SQLAlchemy síncrono fora do loop, um `AsyncClient` por destino

Toda chamada bloqueante (bcrypt, SQL, `resolve_gateway`) sai do event loop da API e do worker. O loop só espera rede. Antes, 10 logins simultâneos seguravam o loop por ~2 s (bcrypt de custo 12 dentro de `async def`) e o `/health`, o Socket.IO e o "digitando…" ficavam parados junto; uma importação de histórico grande fazia o mesmo com SQL.

## Decisão: manter o SQLAlchemy síncrono e tirá-lo do loop

Não migramos para `AsyncSession`. O banco continua síncrono (`create_engine`, `sessionmaker`) e o bloqueio vai para threads:

- **Rota sem `await` é `def`.** O FastAPI a roda no threadpool. Isso vale para quase todas as rotas (agents, menu, companies, contacts, listagens, `login`, `logout`, `/me`) e para as dependências `get_current_user`, `get_optional_user` e `require_superuser`.
- **Rota com `await` e banco é feita em fases.** O banco roda em thread (`run_in_threadpool`/`asyncio.to_thread`), a rede (Evolution, Gateway) roda no loop, e a Session **não segura conexão durante o `await` longo**: a fase de banco copia os escalares de que a fase de rede precisa e termina com `rollback()`/`close()` antes da chamada, e a fase seguinte reabre o que precisa. Nada de ler ORM depois do `rollback()`: ele expira tudo. Exemplos: `send_conversation_message` (`_prepare_send` → `send_text_message` → `_record_sent`), `test_model`, `list_remote_models`, `list_instances`, `status`/`connect`/`logout` da Instance, criar/apagar Instance (`_local_rows`, `instance_evolution_name`, `_delete_target`, `_check_create`). `tests/api/test_instances_no_open_transaction.py` afirma `db.in_transaction() == False` dentro da chamada à Evolution em cada uma. Exceção aceita: `change_status` de pedido (abaixo).
- **Worker e Socket.IO**: os handlers do Socket.IO, o registry de Gateways (`resolve_gateway` no executor), o `send_and_persist` (a Message `from_me` é gravada em thread **antes** de `publish_message`), o rastreio de Handoff e as escritas do history sync vão por `asyncio.to_thread`. No `send_and_persist` a gravação em thread vai sob `asyncio.shield`: se o Turn é cancelado (timeout, shutdown), a task espera a thread commitar antes de soltar o lock `SAVE` e de propagar o cancelamento. Sem isso o eco leria a Message `from_me` sem commit e o `db.close()` do Turn rodaria com a thread usando a mesma Session.
- **bcrypt**: `hash_password`/`verify_password` só são alcançados fora do loop (`def login`, `run_in_threadpool(create_user)` no cadastro).

### Regras do padrão

1. Uma Session é usada por uma thread de cada vez. Os `await` de uma fase são sequenciais; nunca duas `to_thread` na mesma Session ao mesmo tempo.
2. O `commit` expira os atributos. Valor escalar que o código do loop vai ler (ids, `is_superuser`, nome da Instance) é copiado **antes** do commit, ou o objeto é `refresh`ado dentro da thread. Ler atributo expirado no loop dispararia um SELECT lá, justamente o que se quer evitar.
3. Onde a Session é compartilhada com o teste (`client` fixture), a fase de banco termina com `rollback()` e não com `close()`, que expulsaria os objetos da Session.
4. Lock de importação de histórico: o advisory lock do Postgres usa uma conexão própria, tomada e solta em thread.

### Limites aceitos

- **`change_status` de pedido segura a transação durante o aviso.** `_transition` termina com `refresh` e carga de relacionamentos, e o `send_and_persist` precisa desses objetos ORM, então o `rollback()` não serve: a transação fica aberta durante o envio do aviso (até 30 s, o timeout da Evolution). É o mesmo padrão que as rotas de Instance deixaram de ter; só se resolve passando escalares ao `send_and_persist`, o que não coube na #93.
- **O worker ainda faz SQL síncrono no loop** em `executor.build_context`, `_handle_message` (commit e leitura de atributo expirado em `publish_message`) e `get_or_create_*` (`message_store`). O escopo da #93 é a API, o Socket.IO, o Gateway e o history sync.
- **Pool sob carga.** Rotas em fases já não seguram conexão na rede, mas uma fase de banco ainda espera conexão numa thread se as 30 estiverem em uso (o threadpool tem 40 slots).

### Por que não `AsyncSession`

- **Raio de explosão.** `AsyncSession` exige trocar o driver (`asyncpg`), todos os `Session` de modelos, serviços, Tools do Agent e Packs (centenas de consultas síncronas chamadas de dentro do loop do Agent) e reescrever os acessos preguiçosos: um `lazy="select"` num atributo vira `MissingGreenlet`. A suíte inteira roda em SQLite síncrono.
- **O ganho é o mesmo.** O objetivo é o loop livre. Thread resolve isso; o `AsyncSession` só trocaria o jeito de esperar o banco.
- **Custo aceito**: um salto de thread por fase de banco e a disciplina das regras acima. O threadpool padrão do Starlette tem 40 slots; o pool de conexões, 30 (`pool_size=10, max_overflow=20`). Quem passa de 30 espera a conexão numa thread, não no loop.
- **Quando reverter a decisão**: se o número de threads simultâneas passar a ser o gargalo (centenas de requisições esperando conexão), aí a migração compensa. Hoje o atendimento é limitado pelo Gateway, não pelo banco.

## Um `httpx.AsyncClient` por destino

`app/core/http_clients.py`: `get(destino)` devolve o cliente do destino (`evolution:<url>`, `gateway:<raiz da URL>`) e `close_all()` fecha todos. Antes, cada chamada abria e fechava o próprio cliente: handshake TCP/TLS a cada request, inclusive no "digitando…". Agora o pool de conexões (keep-alive) vive o processo inteiro.

- O timeout vai em cada request, não no cliente.
- Ciclo de vida: a API fecha no fim do `lifespan`; o worker, no `finally` de `run()`.
- O cliente fica preso ao event loop que o criou. Só os testes têm mais de um loop por processo (um por teste); outro loop recebe um cliente novo.
- O history sync usa só os métodos públicos do cliente da Evolution (`fetch_chats`, `fetch_groups`, `fetch_contacts`, `fetch_messages_page`), nunca `_request`.

## Intervalo mínimo entre reimportações do histórico

`chats.upsert` e `connection.update` com `open` disparam a importação, e a Evolution repete os dois com frequência. `HISTORY_REIMPORT_MIN_INTERVAL_SECONDS` (padrão 300; 0 desliga) define o intervalo mínimo entre reimportações da mesma Instance. Repetição dentro do intervalo é ignorada com o log `History reimport ignored: …`.

- **Redis `SET NX EX`**, chave `neuralilux:history_reimport:<instance_id>`, TTL igual ao intervalo. É atômico e compartilhado: com N workers, **uma** reimportação por intervalo no total, não uma por worker. Estado em memória daria um relógio por processo.
- **Falha aberta**: Redis fora do ar → reimporta e loga `History reimport guard unavailable; importing anyway`. É o oposto do rate limit de login ([ADR 0008](0008-sessao-em-cookie-httponly.md) e `rate_limit.py` falham fechados) porque os riscos são outros: ali, deixar passar abre força bruta; aqui, bloquear deixaria a Instance sem histórico, e importar demais custa só tempo (a importação é idempotente por `message_id` e uma por vez por Instance, pelo advisory lock do Postgres).
- A chave é gravada ao decidir, não ao terminar: uma importação que falha também espera o intervalo.
- **Circuito curto**: depois de uma falha do Redis, o guarda lembra por `DOWN_BACKOFF_SECONDS` (5 s) e reimporta sem tentar o Redis. Sem isso, cada evento do webhook pagaria até 4 s de timeouts (conexão 2 s + socket 2 s) com o Redis fora.

## Como isso é testado

`tests/loop_helpers.py` liga o modo debug do asyncio com `slow_callback_duration` de 100 ms e captura o log. Os testes afirmam: o login (bcrypt de produção) e um lote de history sync não geram callback lento; 10 logins simultâneos não atrasam o `/health` além de 1,0 s; há um `AsyncClient` por destino durante o processo; uma reimportação repetida no intervalo é ignorada com log.

O teto do `/health` é 1,0 s, não 0,5 s: sem o bcrypt fora do loop o bloqueio medido é de ~1,7 s, mas um host carregado atrasa o prober em centenas de ms por ruído (0,61 s medido com load average 41). 1,0 s fica entre os dois, separa o bloqueio real do ruído, e sem o fix os dois testes continuam falhando (callback de 0,887 s; pior ciclo do prober de 8,33 s).
