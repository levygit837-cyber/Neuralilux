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

Ordem de merge obrigatória: T1 → T4 → T5 → T7 → #31 (0007, já na `main`) → #35 (0008) → (0009 #32 → 0010 #33 → 0011 #34). Antes de mergear, `alembic heads` tem de mostrar uma única head.
