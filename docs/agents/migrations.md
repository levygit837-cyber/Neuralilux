# Cadeia de migrações Alembic

Tickets paralelos não podem criar heads duplicados. A cadeia é fixa:

| Revision | Ticket | `down_revision` |
|---|---|---|
| `0003_remove_super_agent_rag` | T1 | `0002` |
| `0004_conversation_memory` | T4 | `0003_remove_super_agent_rag` |
| `0005_company_operations` | T5 | `0004_conversation_memory` |
| `0006_single_agent` | T7 | `0005_company_operations` |

Ordem de merge obrigatória: T1 → T4 → T5 → T7. Antes de mergear, `alembic heads` tem de mostrar uma única head.
