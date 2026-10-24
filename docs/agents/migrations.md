# Cadeia de migrações Alembic

Tickets paralelos não podem criar heads duplicados. Os ids seguem o padrão do repo (`revision='0002'`): id curto, slug só no nome do arquivo.

| `revision` | `down_revision` | Ticket | Arquivo (sufixo) |
|---|---|---|---|
| `0003` | `0002` | T1 | `0003_remove_super_agent_rag.py` |
| `0004` | `0003` | T4 | `0004_conversation_memory.py` |
| `0005` | `0004` | T5 | `0005_company_operations.py` |
| `0006` | `0005` | T7 | `0006_single_agent.py` |
| `0007` | `0006` | #31 | `0007_conversation_sessions.py` |
| `0008` | `0007` | #35 | `0008_handoff_exit.py` |
| `0009` | `0008` | #32 | `0009_order_recap.py` |
| `0010` | `0009` | #33 | `0010_order_cancel_alter.py` |
| `0011` | `0010` | #34 | `0011_message_sent_by.py` |
| `0012` | `0011` | chat | `0012_chat_history_sync.py` |
| `0013` | `0012` | #76 | `0013_agent_company_instructions.py` |
| `0014` | `0013` | #82 | `0014_remove_products.py` |
| `0015` | `0014` | #90 | `0015_hot_path_indexes.py` |
| `0016` | `0015` | #91 | `0016_turn_state.py` |

Ordem de merge obrigatória: T1 → T4 → T5 → T7 → #31 (0007, já na `main`) → #35 (0008) → (0009 #32 → 0010 #33 → 0011 #34). Antes de mergear, `alembic heads` tem de mostrar uma única head.

## `0015`: fusão de duplicatas e janela de manutenção

A `0015` funde Contacts e Conversations duplicados (mantém o mais antigo e reaponta todos os filhos pelas FKs) antes de criar as unicidades `(instance_id, remote_jid)` e `(instance_id, contact_id)`.

- **Janela de manutenção obrigatória.** Pare a API e o worker antes do `alembic upgrade`. O `upgrade` roda numa transação só: os `CREATE INDEX` de `messages` seguram `SHARE` (bloqueiam escrita) e os `ADD CONSTRAINT UNIQUE` seguram `ACCESS EXCLUSIVE` em `contacts`/`conversations` até o commit. Os índices de `messages` vêm primeiro, para o `ACCESS EXCLUSIVE` só valer no fim. Com a API no ar, um insert concorrente pode recriar uma duplicata depois da fusão e derrubar o `ADD CONSTRAINT`; a migração inteira sofre rollback.
- **Tempo.** Cresce com o tamanho de `messages` (construção dos dois índices e reapontamento das Messages da Conversation fundida).
- **Summary.** Entre dois Summaries da mesma Conversation fundida fica o de maior `message_count`. O `covered_until_message_id` dele vira um cursor sobre Messages intercaladas das Conversations fundidas, então pode sobrar uma lacuna de memória até o próximo `refresh_summary`.
- **Ticket órfão.** Se as Conversations fundidas tinham Tickets abertos diferentes, o que não ficou em `conversations.ticket_id` é fechado (`closed`, como o `release`).
- **Downgrade.** Remove índices e unicidades, mas **não desfaz a fusão**: os registros removidos não voltam. Faça backup antes de aplicar em produção.

## `0016`: estado do Turn por Message

Adiciona `turn_state`, `turn_reason` e `turn_claimed_at` (todas nulas, sem default) e o índice parcial `ix_messages_turn_pending` (`WHERE turn_state = 'pending'`) em `messages`.

- **Sem janela de manutenção.** `ADD COLUMN` nulo sem default é só metadado no Postgres 15 (não reescreve a tabela; `ACCESS EXCLUSIVE` por instantes). O `CREATE INDEX` segura `SHARE` em `messages` (bloqueia escrita, não leitura) durante a construção; como nenhuma Message existente é `pending`, o índice nasce vazio e a construção é só uma varredura da tabela. Aplique fora do pico.
- **Compatibilidade.** O worker antigo ignora as colunas; Messages gravadas por ele ficam com `turn_state` nulo (sem Turn pendente). Aplique a migração antes de subir o worker novo.
- **Downgrade.** Remove índice e colunas; perde o estado das Messages pendentes.

