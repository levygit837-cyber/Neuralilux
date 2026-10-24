# Dashboard: o que cada número significa

Termos conforme o [glossário](../CONTEXT.md). O código está em `backend/app/api/routes/dashboard.py` (rotas) e `backend/app/services/dashboard_service.py` (contas). Métrica sem definição honesta não entra: o dashboard não tem canal, satisfação (CSAT), "taxa de resolução" nem tempo médio de resposta, porque o sistema não registra os dados que essas contas exigiriam (veja [o que não existe](#o-que-não-existe)).

## Escopo e período

- **Escopo.** Só entram as Instances ativas do usuário (`Instance.owner_id`); o superusuário vê todas. É o mesmo filtro de `/conversations` e `/tickets` (`instance_ids_for_user`). Usuário sem Instance vê zeros e taxa de resposta vazia, nunca dados de outro dono.
- **Grupos ficam de fora.** Só contam Conversations 1:1 (`is_group = false`): o Agent nunca fala em grupo.
- **Período** (`period=7d|30d|90d`, padrão `7d`): os últimos N dias, contando hoje. Os dias são locais, no fuso da Company do usuário (`Company.timezone`; sem Company, `America/Sao_Paulo`), e o período começa à meia-noite local do primeiro dia.
- **Período anterior.** Os N dias imediatamente antes do período. É a base de toda tendência: o frontend compara `current` com `previous` e esconde a tendência quando `previous` é zero ou vazio (não há comparação honesta).

## Números

| Número | Rota | Definição |
|---|---|---|
| Conversas novas | `GET /dashboard/overview` → `conversations` | Conversations criadas no período (`Conversation.created_at`). Não é o total acumulado. |
| Messages | `overview` → `messages` | Messages do período (`Message.timestamp`), entrada e saída, incluindo avisos do sistema. |
| Handoffs | `overview` → `handoffs` | Tickets abertos no período (`Ticket.created_at`), qualquer status. Um Ticket é o registro de um Handoff. |
| Taxa de resposta | `overview` → `response_rate` | Das Messages que o Contact enviou no período (`direction = incoming`), a porcentagem que tem depois, na mesma Conversation, uma Message de saída que não seja aviso do sistema (`sent_by = "system"`). Resposta do Agent e de um Attendant contam. `null` se o Contact não escreveu no período. Vem com `received` e `answered`. |
| Conversas por dia | `GET /dashboard/conversations-over-time` | Conversas novas por dia local do período, com os dias sem nenhuma em zero. O agrupamento é feito em Python com o fuso da Company, não com função de data do banco, então dá o mesmo resultado em Postgres e SQLite. |
| Messages por Instance | `GET /dashboard/messages-by-instance` | Messages do período por Instance ativa do escopo, com o nome real dela (`Instance.name`), da mais movimentada para a menos (até 10). Instance sem Message aparece com zero. |
| Handoffs por status | `GET /dashboard/handoffs` | Tickets abertos no período agrupados por status (`open`, `in_progress`, `closed`, `expired`), sempre com as quatro chaves. |

Limites da taxa de resposta: ela mede se *houve* resposta depois, não se foi boa nem quanto demorou. Uma Message que o Contact manda sob Handoff conta como respondida quando o Attendant escreve depois.

## Falha

Erro de banco não vira zero. A rota registra o traceback (`logger.exception`) e responde `500` com `{"detail": "Erro ao carregar os dados do dashboard"}`, sem texto da exceção. Cada widget do frontend é uma query própria e mostra o erro sozinho, com "Tentar de novo"; os outros continuam.

## O que não existe

- **Canal.** Toda Instance é WhatsApp. O gráfico mostra Messages por *Instance*, não por "canal".
- **Satisfação (CSAT).** `Conversation.rating` existe na tabela, mas nada no sistema grava a nota. Uma média de coluna sempre vazia seria inventada.
- **Taxa de resolução / "escaladas".** `is_active` e `is_archived` da Conversation não registram resolução nem escalonamento. O que existe de verdade é o Ticket do Handoff, mostrado em Handoffs por status.
- **Tempo médio de resposta.** Exigiria medir o intervalo até a resposta; hoje só se sabe se houve resposta.
