# Auditoria dos testes do backend: inventário classificado

Inventário da issue #52. Nenhum teste foi removido ou alterado: este arquivo é a entrada dos tickets de remoção.

## Como ler

- Escopo: toda função `test_*` (e método de classe `Classe::test_*`) em `backend/tests/**/test_*.py`. Fixtures e helpers (`conftest.py`, `*_helpers.py`, `agent_fakes.py`) não são testes e ficam de fora.
- Testes parametrizados aparecem em uma linha só, com `(×N casos)` ao lado do nome.
- Cada função foi lida por inteiro, com as fixtures que usa e o código de `backend/app/` quando a asserção dependia dele.
- Critério de `keep`: o teste pegaria um bug plausível visível ao consumidor (comportamento visível ao usuário, fronteira, invariante, transição, precedência ou erro). Na dúvida real, é `keep`.
- Tudo que não é `keep` é candidato a remoção e tem motivo de uma linha. `redundant` cita o teste equivalente que permanece (`arquivo::teste`, ou só o nome quando está no mesmo arquivo).
- Os candidatos são sugestão para os tickets de remoção, não ordem: quem for apagar deve reler o teste e confirmar o equivalente antes.

### Categorias

| Categoria | Significado |
|---|---|
| `keep` | protege comportamento visível ao usuário, fronteira, invariante, transição, precedência ou erro |
| `redundant` | mesmo caminho e mesma asserção de outro teste (citado) |
| `stub` | vazio, `pass`, `assert True`, só `is not None` |
| `wiring` | só confere repasse, mock que ecoa o que recebeu, cópia de campos |
| `wording` | fixa texto, implementação ou default incidental |
| `extreme` | caso de borda sem consequência real |
| `dead-e2e` | e2e que não roda nem tem como rodar |

## Totais

Contagem por linha de tabela (uma linha por função; parametrizado conta uma vez).

| Área | Arquivos | Funções | `keep` | `redundant` | `stub` | `wiring` | `wording` | `extreme` | `dead-e2e` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| api / core / models | 19 | 195 | 193 | 1 | 0 | 0 | 1 | 0 | 0 |
| whatsapp / realtime (após #54) | 21 | 152 | 152 | 0 | 0 | 0 | 0 | 0 | 0 |
| agent / packs / handoff / llm / scripts (após #55) | 28 | 327 | 327 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | 70 | 745 | **665** | **37** | **13** | **17** | **13** | **0** | **0** |

- Candidatos a remoção: 80 de 745 funções.
- `dead-e2e` é zero de propósito: `tests/whatsapp/test_whatsapp_actions.py` é o único arquivo marcado `e2e` (pulado sem `RUN_E2E=1`). Todos os métodos do client que ele chama existem com a assinatura usada e uma Evolution API respondeu em `localhost:8081` durante a auditoria; falta só uma `EVOLUTION_API_KEY` válida, então o arquivo é executável (o `.py` não foi rodado com `RUN_E2E=1`). As funções fracas dele estão como `stub`/`wiring`.
- `test_instance` em `test_whatsapp_actions.py` é fixture (nome casa com `test_*`), não teste, e não entra na contagem.

## Cobertura base

Comando (de `backend/`, sem `DATABASE_URL`/`EVOLUTION_API_KEY`, SQLite):

```sh
env -u DATABASE_URL -u EVOLUTION_API_KEY ./venv/bin/python -m pytest tests --ignore=tests/e2e -q -p no:cacheprovider --cov=app --cov-report=term-missing:skip-covered
```

- Resultado: `913 passed, 24 skipped` em 9m18s. Os 24 skips são `tests/whatsapp/test_whatsapp_actions.py` (e2e, sem `RUN_E2E=1`).
- Total de `app/`: **85.5%** (6432 linhas executáveis, 933 sem cobertura). Só cobertura de linha, sem branch.

| Módulo | Linhas | Não cobertas | Cobertura |
|---|---:|---:|---:|
| `app/agent` | 658 | 19 | 97% |
| `app/api` | 1256 | 238 | 81% |
| `app/core` | 138 | 3 | 98% |
| `app/llm` | 209 | 6 | 97% |
| `app/main.py` | 38 | 9 | 76% |
| `app/models` | 479 | 0 | 100% |
| `app/packs` | 687 | 16 | 98% |
| `app/realtime` | 348 | 106 | 70% |
| `app/schemas` | 679 | 51 | 92% |
| `app/services` | 789 | 304 | 61% |
| `app/whatsapp` | 1151 | 181 | 84% |
| **`app/` (total)** | **6432** | **933** | **85.5%** |

Arquivos de `app/` abaixo de 60% (os tickets de remoção não devem derrubar mais cobertura nestes):

| Arquivo | Linhas | Não cobertas | Cobertura |
|---|---:|---:|---:|
| `app/schemas/instance.py` | 44 | 44 | 0% |
| `app/services/delivery_zone_service.py` | 76 | 76 | 0% |
| `app/services/menu/lookup.py` | 79 | 79 | 0% |
| `app/api/routes/dashboard.py` | 111 | 89 | 20% |
| `app/services/menu/sync.py` | 50 | 39 | 22% |
| `app/services/product_service.py` | 33 | 23 | 30% |
| `app/whatsapp/evolution_history.py` | 28 | 19 | 32% |
| `app/realtime/event_bus.py` | 65 | 39 | 40% |
| `app/api/routes/products.py` | 39 | 21 | 46% |
| `app/api/routes/conversations/contacts.py` | 28 | 15 | 46% |
| `app/whatsapp/message_queue.py` | 121 | 60 | 50% |

O relatório por arquivo completo sai do mesmo comando com `--cov-report=term-missing`.

## Candidatos a remoção

Resumo de tudo que não é `keep`, por área. O detalhe e o contexto de cada linha estão nas tabelas por arquivo, mais abaixo.

### Área 1: api / core / models

| Arquivo | Teste | Categoria | Motivo / equivalente |
|---|---|---|---|
| `api/test_company_session_timeout.py` | `test_company_session_timeout_can_be_changed` | `redundant` | Mesmo `update_company` e mesma releitura de `session_timeout_minutes`: `tests/api/test_company_settings.py::test_owner_saves_every_company_field_and_reloads_them` (envia 90 e confere no GET).  **Removido na #53.**|
| `api/test_company_session_timeout.py` | `test_company_timezone_can_be_changed_to_a_valid_zone` | `redundant` | Mesmo `update_company` com `timezone="America/Fortaleza"`: `tests/api/test_company_settings.py::test_owner_saves_every_company_field_and_reloads_them`.  **Removido na #53.**|
| `api/test_company_session_timeout.py` | `test_session_timeout_must_be_positive (×2 casos)` | `redundant` | Mesma validação `ge=1` do schema: `tests/api/test_company_settings.py::test_invalid_values_are_422_and_nothing_is_saved` (caso `session_timeout_minutes: 0`); `-5` é o mesmo ramo.  **Removido na #53.**|
| `api/test_company_settings.py` | `test_minimum_order_rejects_non_finite_values (×3 casos)` | `redundant` | Mesma recusa de NaN/Infinity/-Infinity (`allow_inf_nan=False`): `tests/api/test_company_settings.py::test_invalid_values_are_422_and_nothing_is_saved` (casos `"NaN"`, `"Infinity"`, `"-Infinity"`).  **Removido na #53.**|
| `api/test_conversations_human_in_loop.py` | `test_list_reflects_human_in_loop_flag` | `redundant` | Mesma asserção de `human_in_loop` True/False na listagem: `tests/handoff/test_handoff_api.py::test_state_survives_reload_through_the_listing`.  **Removido na #53.**|
| `api/test_conversations_human_in_loop.py` | `test_release_control_clears_flag_in_list` | `redundant` | Liberar e ver `human_in_loop` False na listagem já está em `tests/handoff/test_handoff_api.py::test_state_survives_reload_through_the_listing`.  **Removido na #53.**|
| `api/test_gateways_api.py` | `test_patching_same_base_url_keeps_saved_api_key_without_resending_it` | `redundant` | Mesmo ramo (origem igual, sem `api_key` no corpo): `tests/api/test_gateways_api.py::test_changing_only_the_path_keeps_saved_api_key_without_resending_it`.  **Removido na #53.**|
| `api/test_gateways_api.py` | `test_remote_models_other_errors_are_bad_gateway` | `redundant` | Mesmo mapeamento de erro do Gateway para 502: `tests/api/test_gateways_api.py::test_remote_models_uses_single_attempt_and_15s_timeout` (429 dá 502).  **Mantido na #53:** o equivalente citado cai em `LLMRateLimitError` (429, ramo `except LLMError`); este exercita `LLMProviderError` com 403 (ramo próprio da rota, `exc.status_code != 404`).|
| `api/test_instance_agent_status.py` | `test_patch_agent_status_updates_flag_of_existing_instance` | `wiring` | Envia `agent_enabled: False` a uma Instance que já está False e confere False; só ecoa, sem transição.  **Removido na #53.**|
| `api/test_instances_access.py` | `test_agent_binding_unbind_survives_later_requests` | `redundant` | Mesmo unbind com `agent_id` None e `agent_enabled` False: `tests/api/test_instance_agent_status.py::test_patch_agent_binding_unbinds_agent_and_disables_auto_reply`.  **Removido na #53.**|
| `api/test_main.py` | `test_root` | `wording` | Fixa o texto literal `"Neuralilux API"` da mensagem da raiz; nada além de 200 é contrato  **Mantido na #53:** é o único teste que chama `GET /`; apagá-lo tira a rota `root` de `app/main.py` da cobertura. Fortalecido: a asserção do texto literal virou `version` não vazio.|
| `api/test_menu_management_endpoints.py` | `test_create_item_with_sku_and_stock` | `redundant` | POST de item com `sku`/`stock_quantity` e mesmas asserções já feitos em `tests/api/test_menu_management_endpoints.py::test_create_and_update_item_with_custom_attributes` (criação) e `::test_list_menu_includes_sku_and_stock`  **Removido na #53.**|
| `api/test_order_refunds.py` | `test_already_refunded_record_still_answers_200` | `redundant` | Baixar registro já `refunded` e receber 200/`refunded` é a 2ª chamada de `tests/api/test_order_refunds.py::test_marking_the_same_refund_twice_is_idempotent`  **Removido na #53.**|
| `api/test_order_status.py` | `test_panel_lists_newest_first_and_honours_limit` | `redundant` | Ordem `A-4, A-3` e `limit` já cobertos por `tests/api/test_order_status.py::test_offset_and_limit_page_through_the_filtered_list_with_the_total` e `::test_status_filter_splits_active_from_finished_and_all_lists_everything`  **Removido na #53.**|
| `core/test_access_log_redaction.py` | `test_records_with_unexpected_args_pass_through` | `redundant` | Apesar do nome, usa tupla de `str` sem `token=` (não exercita args não-tuple/não-str); mesmo caminho e asserção de `tests/core/test_access_log_redaction.py::test_other_paths_are_left_untouched`.  **Removido na #53.**|
| `models/test_payment_record_model.py` | `TestPaymentRecordModel::test_create_payment_record` | `wiring` | Só relê os campos que acabou de gravar (`amount == 100.00`, `pix_key`, `status == "pending"`); nenhuma regra/constraint/default de negócio, e o caminho é exercido por `tests/packs/test_pack_pix.py`.  **Removido na #53.**|
| `models/test_payment_record_model.py` | `TestPaymentRecordModel::test_payment_record_expired_status` | `wiring` | `assert payment.status == "expired"` ecoa o valor gravado; não testa transição nem o índice único.  **Removido na #53.**|
| `models/test_payment_record_model.py` | `TestPaymentRecordModel::test_payment_record_paid_status` | `wiring` | `assert payment.status == "paid"` e `paid_at is not None` apenas ecoam o que foi passado ao construtor.  **Removido na #53.**|
| `models/test_payment_record_model.py` | `TestPaymentRecordModel::test_payment_record_relationships` | `wiring` | Só confere `payment.order.id == order.id` / `payment.conversation.id`; esses relationships não são usados em `app/`.  **Removido na #53.**|
| `models/test_ticket_model.py` | `TestTicketModel::test_create_ticket` | `wiring` | Copia 8 campos e relê (`agent_type == "sac"`, `status == "open"`); sem regra de negócio, Ticket já é exercido em `tests/handoff/*`.  **Removido na #53.**|
| `models/test_ticket_model.py` | `TestTicketModel::test_ticket_relationships` | `wiring` | Só confere `ticket.conversation.id == conversation.id` (e instance/contact); mapeamento ORM sem comportamento.  **Removido na #53.**|
| `models/test_ticket_model.py` | `TestTicketModel::test_ticket_sales_agent_type` | `wiring` | `assert ticket.agent_type == "sales"` ecoa o valor passado ao construtor.  **Removido na #53.**|
| `models/test_ticket_model.py` | `TestTicketModel::test_ticket_with_assigned_user` | `wiring` | `ticket.assigned_to == user.id` e `status == "in_progress"` apenas ecoam a entrada.  **Removido na #53.**|

Ticket #53 (área 1): 21 funções removidas, as marcadas **Removido na #53**; os 3 arquivos que ficaram sem teste (`test_conversations_human_in_loop.py`, `test_payment_record_model.py`, `test_ticket_model.py`) foram apagados. Duas ficam, com a razão na própria linha (**Mantido na #53**). `tests/api/test_handoff_event_bus.py` (2 `keep`) é novo: cobre o `publish_event` real de `handoff_service` (antes só exercido pelos testes removidos) e a falha do bus. Os cabeçalhos por arquivo (`N testes: ...`) seguem a contagem da #52; a linha da Área 1 em Totais já reflete o estado pós-#53. A linha **Total** acima não foi recalculada aqui: soma as três áreas depois que as três PRs entrarem.

### Área 2: whatsapp / realtime

| Arquivo | Teste | Categoria | Motivo / equivalente |
|---|---|---|---|
| `realtime/test_socket_thinking_events.py` | `test_event_without_instance_is_dropped` | `redundant` | O descarte por falta de `instance_name` é o mesmo `return` inicial de `emit_realtime_event` coberto por `tests/agent/test_handoff_socket.py::test_handoff_event_without_instance_is_dropped_like_other_events`. **Removido (#54).** |
| `realtime/test_socket_thinking_events.py` | `test_handoff_request_reaches_both_rooms_with_ticket_and_reason` | `redundant` | Mesmas salas e `ticketId`/`reason` no socket que `tests/agent/test_handoff_socket.py::test_handoff_event_from_the_tool_reaches_instance_and_conversation_rooms`, que parte da Tool real; aqui só passa por `publish_handoff_requested`, helper sem chamador em `app/`. **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestEvolutionAPIError::test_default_status_code` | `wording` | Fixa o default incidental `status_code == 500` do construtor **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestEvolutionAPIError::test_message_and_code` | `wiring` | Só relê atributos que o `__init__` acabou de atribuir (`err.message`, `err.status_code`, `str(err)`) **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestEvolutionAPIService::test_init_sets_base_url_and_headers` | `stub` | Só `base_url is not None` e chaves presentes em `headers`, sem checar valor **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchChats::test_correct_url` | `redundant` | URL já é exigida pela rota respx de todo teste da classe. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchChats::test_sends_empty_json_body` **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchChats::test_returns_chat_list` | `wiring` | `result == chats`: só repassa o JSON do mock **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchChats::test_uses_post_method` | `redundant` | Rota respx já é `post`; `method == "POST"` é tautologia. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchChats::test_sends_empty_json_body` **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchContacts::test_correct_url` | `redundant` | URL já é exigida pela rota respx. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchContacts::test_sends_empty_json_body` **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchContacts::test_returns_contacts` | `wiring` | `result == contacts`: só repassa o JSON do mock **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchContacts::test_uses_post_method` | `redundant` | Rota respx já é `post`. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchContacts::test_sends_empty_json_body` **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchMessages::test_correct_url` | `redundant` | URL já é exigida pela rota respx. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchMessages::test_sends_correct_payload` **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchMessages::test_default_offset` | `wording` | Fixa o default incidental `limit == 20` **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchMessages::test_returns_messages` | `wiring` | `result == response_data`: só repassa o JSON do mock **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestFetchMessages::test_uses_post_method` | `redundant` | Rota respx já é `post`. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchMessages::test_sends_correct_payload` **Removido (#54).** |
| `whatsapp/test_evolution_service.py` | `TestSendTextMessage::test_uses_post_method` | `redundant` | Rota respx já é `post`. Equivalente: `tests/whatsapp/test_evolution_service.py::TestSendTextMessage::test_strips_jid_suffix` **Removido (#54).** |
| `whatsapp/test_history_sync_trigger.py` | `test_worker_skips_silently_when_another_process_is_importing` | `wording` | Só `consumer._syncing == set()` (atributo interno); passa igual se `SyncAlreadyRunning` cair no `except Exception`, já coberto pelo teste de falha **Mantido (#54):** reforçado e renomeado para `test_worker_skips_with_an_info_log_when_another_process_is_importing`; agora afirma o log informativo, a ausência de `logger.exception` e a Instance liberada. Passa a `keep`. |
| `whatsapp/test_realtime_bridge.py` | `test_save_message_to_database_does_not_trigger_agent_when_instance_is_disabled` | `redundant` | Mesma asserção (`agent_enabled=False` ⇒ sem Turn nem envio). Equivalente: `tests/whatsapp/test_whatsapp_consumer.py::test_disabled_agent_does_not_answer` **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestConnectionStatus::test_get_instance_status_valid_states` | `stub` | `state in valid_states or isinstance(state, str)` é tautologia **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestEvolutionAPIConnectivity::test_api_base_url_configured` | `stub` | `"localhost:8081" in url or "http" in url` é tautologia **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestEvolutionAPIConnectivity::test_api_is_reachable` | `stub` | Só falha se a Evolution estiver fora do ar; testa ambiente, não código **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestEvolutionAPIConnectivity::test_api_key_configured` | `wiring` | Confere só que `settings.EVOLUTION_API_KEY` chegou a `api_key` **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestEvolutionAPIConnectivity::test_headers_contain_apikey` | `wiring` | Cópia `api_key`→`headers["apikey"]`; header já enviado em `test_evolution_service.py::TestFetchChats::test_sends_apikey_header` **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestInstanceLifecycle::test_create_and_delete_instance` | `stub` | Só `is not None` nos dois retornos; erro HTTP já levantaria sozinho **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestInstanceLifecycle::test_create_duplicate_instance_handled` | `stub` | Passa se o segundo create tiver sucesso ou falhar com 4 códigos; sem asserção sobre o tratamento **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestListChats::test_fetch_chats_response_structure` | `stub` | `... or isinstance(chat, dict)` é tautologia; vazio se não há chats **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestListChats::test_fetch_chats_with_valid_instance` | `stub` | Só `assert result is not None`; já coberto pelo `returns_list` **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestListContacts::test_fetch_contacts_response_structure` | `stub` | `isinstance(contact, dict)` só se houver contato; instância nova é vazia **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestListContacts::test_fetch_contacts_with_valid_instance` | `stub` | Só `assert result is not None`; já coberto pelo `returns_list` **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestReadMessages::test_fetch_messages_default_offset` | `stub` | Docstring fala em offset 20 mas só assere `is not None` (payload já em `test_evolution_service.py::TestFetchMessages::test_default_offset`) **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestReadMessages::test_fetch_messages_with_pagination` | `stub` | Só `assert result is not None`; `page` é ignorado pelo client **Removido (#54).** |
| `whatsapp/test_whatsapp_actions.py` | `TestSendMessage::test_send_text_message_accepts_request` | `stub` | Engole status 500 (caso normal sem WhatsApp conectado); quase nunca assere nada **Removido (#54).** |

### Área 3: agent / packs / handoff / llm / scripts

Issue #55: 21 testes removidos nesta área. Quatro candidatos foram relidos e mantidos porque o equivalente citado não cobre o mesmo comportamento (ou aponta de volta para o próprio teste):

- `test_handoff_publica_um_dict`: `publish_handoff_requested` só tem este teste de pé; o equivalente em `tests/realtime/test_socket_thinking_events.py` é candidato da Área 2 e aponta para cá.
- `test_handoff_event_without_instance_is_dropped_like_other_events`: o equivalente em `tests/realtime/test_socket_thinking_events.py` é candidato da Área 2 e aponta para cá; sobra só este para o descarte sem `instance_name`.
- `test_six_tools_in_total`: nenhum outro teste monta um `ToolRegistry` com as Tools reais do núcleo e do Pack; `from_packs` só recusa duplicata nos testes com Packs falsos.
- `test_secret_key_is_derived_with_hkdf_not_plain_sha256`: único teste que prova que `decrypt_secret` recusa token SHA-256 legado; `test_llm_registry.py::test_reencrypt_*` só prova a migração.

## Inventário por arquivo

### Área 1: api / core / models

#### `tests/api/test_company_session_timeout.py`
5 testes: 2 keep, 3 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_company_session_timeout_can_be_changed`|`redundant`|Mesmo `update_company` e mesma releitura de `session_timeout_minutes`: `tests/api/test_company_settings.py::test_owner_saves_every_company_field_and_reloads_them` (envia 90 e confere no GET). **Removido na #53.**|
|`test_session_timeout_must_be_positive (×2 casos)`|`redundant`|Mesma validação `ge=1` do schema: `tests/api/test_company_settings.py::test_invalid_values_are_422_and_nothing_is_saved` (caso `session_timeout_minutes: 0`); `-5` é o mesmo ramo. **Removido na #53.**|
|`test_update_rejects_a_timezone_zoneinfo_cannot_load (×4 casos)`|`keep`|Recusa `../x`, vazio e `None` (coluna NOT NULL); o teste de API só cobre `Marte/Olympus`.|
|`test_create_rejects_a_timezone_zoneinfo_cannot_load (×3 casos)`|`keep`|Fuso inválido na criação (`CompanyCreate`), caminho que nenhum outro teste exercita.|
|`test_company_timezone_can_be_changed_to_a_valid_zone`|`redundant`|Mesmo `update_company` com `timezone="America/Fortaleza"`: `tests/api/test_company_settings.py::test_owner_saves_every_company_field_and_reloads_them`. **Removido na #53.**|

#### `tests/api/test_company_settings.py`
28 testes: 27 keep, 1 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_owner_saves_every_company_field_and_reloads_them`|`keep`|Salvar e recarregar todos os campos da Company.|
|`test_a_partial_update_keeps_the_other_fields`|`keep`|PUT parcial não apaga campos não enviados.|
|`test_blank_text_clears_the_field`|`keep`|Texto em branco limpa o campo (vira None).|
|`test_minimum_order_and_hours_can_be_cleared`|`keep`|Pedido mínimo e horários aceitam null explícito.|
|`test_another_company_gets_403_and_nothing_changes (×2 casos)`|`keep`|Usuário de outra Company ou sem Company não edita.|
|`test_another_company_cannot_read (×2 casos)`|`keep`|Isolamento de leitura entre Companies.|
|`test_a_regular_user_cannot_create_a_company (×3 casos)`|`keep`|Só superusuário cria Company, sem efeito colateral.|
|`test_anonymous_cannot_create_a_company`|`keep`|Criação sem login dá 401 e não grava.|
|`test_superuser_creates_a_company`|`keep`|Caminho feliz da criação pelo superusuário.|
|`test_only_a_superuser_deactivates_a_company (×3 casos)`|`keep`|Nem o dono desativa a própria Company.|
|`test_superuser_deactivates_a_company`|`keep`|Soft delete: 204 e `is_active` False.|
|`test_deleting_a_missing_company_is_404_for_the_superuser`|`keep`|Erro 404 ao desativar Company inexistente.|
|`test_owner_cannot_change_superuser_only_fields (×2 casos)`|`keep`|Dono não altera `is_active` nem `business_type_id`.|
|`test_anonymous_gets_401`|`keep`|PUT sem login é recusado.|
|`test_superuser_edits_any_company`|`keep`|Superusuário edita Company de terceiros.|
|`test_missing_company_is_404_for_the_superuser`|`keep`|PUT em Company inexistente dá 404.|
|`test_list_shows_only_the_own_company_unless_superuser (×4 casos)`|`keep`|Escopo da listagem por usuário e superusuário.|
|`test_invalid_values_are_422_and_nothing_is_saved (×37 casos)`|`keep`|Validação de horários, pedido mínimo, Pix, fone, timeouts, sem gravação parcial.|
|`test_every_pix_key_kind_is_accepted (×5 casos)`|`keep`|Aceita e-mail, UUID, celular, CPF e CNPJ.|
|`test_overnight_interval_is_accepted_and_kept_as_typed`|`keep`|Intervalo que cruza meia-noite é aceito sem normalizar.|
|`test_common_phone_formats_are_accepted (×4 casos)`|`keep`|Formatos comuns de telefone não são recusados.|
|`test_minimum_order_accepts_zero_up_to_the_ceiling (×3 casos)`|`keep`|Limites 0 e 100000 do pedido mínimo.|
|`test_minimum_order_rejects_non_finite_values (×3 casos)`|`redundant`|Mesma recusa de NaN/Infinity/-Infinity (`allow_inf_nan=False`): `tests/api/test_company_settings.py::test_invalid_values_are_422_and_nothing_is_saved` (casos `"NaN"`, `"Infinity"`, `"-Infinity"`). **Removido na #53.**|
|`test_owner_saves_and_reloads_agent_settings`|`keep`|Salvar e recarregar temperatura e max_tokens do Agent.|
|`test_agent_temperature_can_go_back_to_the_gateway_default`|`keep`|Temperatura volta a None (usa a do Gateway).|
|`test_invalid_agent_settings_are_422 (×5 casos)`|`keep`|Limites de temperatura e max_tokens, e null em max_tokens.|
|`test_agent_of_another_company_is_403 (×2 casos)`|`keep`|Agent de outra Company não é lido nem editado.|
|`test_company_without_agent_is_404`|`keep`|Company sem Agent responde 404.|

#### `tests/api/test_company_settings_reach_agent.py`
2 testes: 2 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_info_empresa_returns_what_the_panel_saved`|`keep`|Config salva no painel chega ao `info_empresa` do Agent.|
|`test_pix_is_accepted_at_closing_once_the_panel_saves_a_key`|`keep`|Chave Pix salva passa a valer no fechamento.|

#### `tests/api/test_conversations_chat_list.py`
14 testes: 14 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_categories_filter_as_specified`|`keep`|Filtro por categoria: all, unread, groups, human, ai.|
|`test_ai_category_is_empty_when_the_instance_agent_is_disabled`|`keep`|Categoria `ai` vazia com Agent da Instance desligado.|
|`test_list_exposes_is_group_and_rejects_unknown_category`|`keep`|Expõe `is_group` e dá 422 em categoria inválida.|
|`test_search_matches_name_and_last_message_without_duplicates`|`keep`|Busca por nome e prévia sem duplicar linha.|
|`test_counts_ignore_archived_and_badge_skips_group_unread`|`keep`|Contadores ignoram arquivadas e o selo ignora grupo.|
|`test_counts_require_instance_and_ownership`|`keep`|`instance_id` obrigatório e 403 para outro dono.|
|`test_read_zeroes_unread_and_checks_owner`|`keep`|Marcar lida zera contador, 403 e 404.|
|`test_sync_requires_a_connected_instance`|`keep`|Sincronizar Instance desconectada dá 400.|
|`test_sync_returns_created_rows_and_maps_evolution_errors`|`keep`|Retorno da sync e erro da Evolution vira 502.|
|`test_sync_returns_409_when_another_process_is_importing`|`keep`|Sync concorrente responde 409.|
|`test_sync_returns_409_not_500_when_the_batch_keeps_conflicting`|`keep`|IntegrityError na sync vira 409, não 500.|
|`test_sync_of_another_users_instance_is_forbidden`|`keep`|Sync de Instance alheia dá 403.|
|`test_sending_to_a_group_passes_the_full_jid`|`keep`|Envio a grupo usa JID completo e grava Message.|
|`test_presence_and_text_use_full_group_jid_but_digits_for_people`|`keep`|`@g.us` e `@lid` com JID inteiro, pessoas só dígitos.|

#### `tests/api/test_conversations_human_in_loop.py`
2 testes: 2 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_list_reflects_human_in_loop_flag`|`redundant`|Mesma asserção de `human_in_loop` True/False na listagem: `tests/handoff/test_handoff_api.py::test_state_survives_reload_through_the_listing`. **Removido na #53.**|
|`test_release_control_clears_flag_in_list`|`redundant`|Liberar e ver `human_in_loop` False na listagem já está em `tests/handoff/test_handoff_api.py::test_state_survives_reload_through_the_listing`. **Removido na #53.**|

#### `tests/api/test_gateways_api.py`
31 testes: 29 keep, 2 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_requires_authentication`|`keep`|Listagem de Gateways exige login (401).|
|`test_api_key_is_encrypted_at_rest_and_never_returned`|`keep`|Chave cifrada no banco e nunca devolvida.|
|`test_patch_api_key_semantics_keep_replace_remove`|`keep`|PATCH da chave: ausente mantém, valor troca, vazio remove.|
|`test_rejects_invalid_base_url (×3 casos)`|`keep`|`base_url` sem esquema http(s) dá 422.|
|`test_duplicate_gateway_and_model_names_conflict`|`keep`|Nomes duplicados de Gateway e modelo dão 409.|
|`test_invalid_reasoning_effort_is_rejected`|`keep`|`reasoning_effort` fora do enum dá 422.|
|`test_assignment_lifecycle_and_cascade_on_model_delete`|`keep`|Atribuição some ao apagar o modelo.|
|`test_cannot_assign_inactive_model`|`keep`|Modelo inativo não pode ser atribuído (400).|
|`test_unknown_agent_type_is_rejected`|`keep`|Tipo de Agent desconhecido dá 422.|
|`test_deleting_gateway_removes_models_and_assignments`|`keep`|Apagar Gateway remove modelos e atribuições.|
|`test_non_superuser_cannot_create_gateway`|`keep`|Usuário comum não cria Gateway (SSRF).|
|`test_non_superuser_is_forbidden_on_every_mutation_and_probe`|`keep`|Todas as rotas de escrita e probe dão 403.|
|`test_non_superuser_can_still_read_gateways_without_secrets`|`keep`|Leitura permitida sem vazar a chave.|
|`test_base_url_rejects_userinfo_and_non_http_schemes (×4 casos)`|`keep`|Recusa userinfo e esquemas file/gopher no POST e no PATCH.|
|`test_gateway_name_must_not_be_blank_after_strip (×3 casos)`|`keep`|Nome em branco após strip dá 422 no POST e no PATCH.|
|`test_gateway_name_is_stored_stripped`|`keep`|Nome é salvo sem espaços nas pontas.|
|`test_changing_base_url_without_new_api_key_is_rejected`|`keep`|Trocar origem sem reenviar chave dá 422 e não grava.|
|`test_changing_base_url_with_new_api_key_replaces_both`|`keep`|Nova origem com nova chave troca ambas.|
|`test_changing_base_url_with_explicit_empty_api_key_erases_the_saved_key`|`keep`|Chave vazia explícita apaga a chave salva.|
|`test_patching_same_base_url_keeps_saved_api_key_without_resending_it`|`redundant`|Mesmo ramo (origem igual, sem `api_key` no corpo): `tests/api/test_gateways_api.py::test_changing_only_the_path_keeps_saved_api_key_without_resending_it`. **Removido na #53.**|
|`test_model_probe_calls_v1_messages_with_max_tokens_8`|`keep`|Probe usa `/v1/messages`, `max_tokens` 8 e esforço do modelo.|
|`test_model_probe_reports_gateway_failure_as_not_ok`|`keep`|Falha HTTP 401 vira `ok` False com erro.|
|`test_remote_models_reads_v1_models`|`keep`|Lista modelos de `/v1/models`.|
|`test_remote_models_404_falls_back_to_registered_models`|`keep`|404 do Gateway cai nos modelos cadastrados.|
|`test_remote_models_other_errors_are_bad_gateway`|`redundant`|Mesmo mapeamento de erro do Gateway para 502: `tests/api/test_gateways_api.py::test_remote_models_uses_single_attempt_and_15s_timeout` (429 dá 502). **Mantido na #53:** o equivalente citado cai em `LLMRateLimitError` (429, ramo `except LLMError`); este exercita `LLMProviderError` com 403 (ramo próprio da rota, `exc.status_code != 404`).|
|`test_changing_only_the_path_keeps_saved_api_key_without_resending_it`|`keep`|Mudar só o path não exige reenviar a chave.|
|`test_changing_scheme_host_or_port_requires_new_api_key (×4 casos)`|`keep`|Esquema, host ou porta diferentes exigem nova chave.|
|`test_changing_only_host_letter_case_is_the_same_origin`|`keep`|Host em outra caixa é a mesma origem.|
|`test_gateway_timeout_defaults_to_60_seconds`|`keep`|Padrão de 60 s documentado em `docs/operations.md`.|
|`test_model_probe_uses_single_attempt_and_15s_timeout`|`keep`|Probe sem retry (1 requisição) com timeout curto.|
|`test_remote_models_uses_single_attempt_and_15s_timeout`|`keep`|Listagem remota sem retry; 429 dá 502.|

#### `tests/api/test_handoff_event_bus.py`
Arquivo novo da #53. 2 testes: 2 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_take_and_release_publish_handoff_updated_on_the_event_bus`|`keep`|Assumir e devolver anunciam `handoff_updated` (`assumed`, `released`) no `realtime_event_bus` de verdade, sem o fixture que troca `publish_event`.|
|`test_event_bus_failure_does_not_undo_the_release`|`keep`|Bus fora do ar não desfaz a devolução: API responde 200 e a Conversation volta ao Agent.|

#### `tests/api/test_instance_agent_status.py`
6 testes: 5 keep, 1 wiring.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_get_agent_status_returns_the_owners_instance_without_writing`|`keep`|Payload do status do Agent da Instance.|
|`test_patch_agent_status_updates_flag_of_existing_instance`|`wiring`|Envia `agent_enabled: False` a uma Instance que já está False e confere False; só ecoa, sem transição. **Removido na #53.**|
|`test_patch_agent_status_requires_bound_agent_to_enable`|`keep`|Ligar sem Agent vinculado dá 400.|
|`test_patch_agent_binding_assigns_agent_and_allows_enabling`|`keep`|Vincular Agent e depois ligar o auto-reply.|
|`test_patch_agent_binding_unbinds_agent_and_disables_auto_reply`|`keep`|Desvincular Agent desliga o auto-reply.|
|`test_list_agents_returns_only_active_agents_available_to_current_user`|`keep`|Lista só Agents ativos próprios ou compartilhados.|

#### `tests/api/test_instances_access.py`
33 testes: 32 keep, 1 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_instance_routes_require_login (×9 casos)`|`keep`|Toda rota de Instance exige login e não chama a Evolution.|
|`test_status_of_another_owners_instance_is_403`|`keep`|Status de Instance alheia dá 403 sem chamar a Evolution.|
|`test_owner_reads_status_by_name`|`keep`|Dono lê o status pelo nome.|
|`test_unknown_instance_is_404`|`keep`|Instance inexistente dá 404.|
|`test_connect_and_logout_of_another_owners_instance_are_403`|`keep`|Connect e logout alheios dão 403 sem efeito.|
|`test_delete_of_another_owners_instance_is_403_and_keeps_it`|`keep`|Delete alheio dá 403 e mantém a Instance ativa.|
|`test_owner_delete_removes_in_evolution_and_deactivates_locally`|`keep`|Delete remove na Evolution e desativa local.|
|`test_superuser_reaches_any_instance`|`keep`|Superusuário acessa Instance de qualquer dono.|
|`test_agent_routes_of_another_owners_instance_are_403_without_changes (×3 casos)`|`keep`|Rotas de Agent alheias dão 403 sem mudar nada.|
|`test_list_returns_only_own_instances_and_never_the_evolution_token`|`keep`|Listagem por dono sem vazar token da Evolution.|
|`test_create_upserts_local_instance_with_owner_company_and_company_agent`|`keep`|Criação grava dono, Company e Agent da Company.|
|`test_create_without_company_agent_leaves_agent_unset`|`keep`|Sem Agent na Company, Instance fica sem Agent e desligada.|
|`test_local_row_is_written_only_after_evolution_created_the_instance`|`keep`|Linha local só após a Evolution criar.|
|`test_create_failure_in_evolution_leaves_no_local_row`|`keep`|Falha na Evolution dá 502 sem linha local.|
|`test_create_over_another_owners_instance_is_403_before_calling_evolution`|`keep`|POST sobre Instance alheia dá 403 antes da Evolution.|
|`test_regular_user_gets_409_when_evolution_already_has_the_name`|`keep`|Nome já usado na Evolution dá 409 ao usuário comum.|
|`test_superuser_imports_an_instance_that_already_exists_in_evolution`|`keep`|Superusuário importa Instance já existente na Evolution.|
|`test_concurrent_create_returns_409_and_rolls_back`|`keep`|Corrida na criação: 409, rollback e órfã apagada.|
|`test_failed_orphan_cleanup_is_logged_and_never_masks_the_409`|`keep`|Falha ao apagar órfã não esconde o 409.|
|`test_conflict_on_an_instance_that_already_existed_in_evolution_does_not_delete_it`|`keep`|Não apaga na Evolution Instance que já existia.|
|`test_unowned_instance_is_403_for_a_regular_user_on_every_route`|`keep`|Instance sem dono é 403 em todas as rotas.|
|`test_superuser_claims_unowned_instance_with_owner_company_and_agent`|`keep`|Superusuário assume Instance sem dono.|
|`test_agent_status_on_a_name_without_row_is_404_and_creates_nothing`|`keep`|GET em nome sem linha dá 404 e não cria.|
|`test_patch_agent_status_and_binding_on_a_name_without_row_are_404_and_create_nothing`|`keep`|PATCH em nome sem linha dá 404 e não cria.|
|`test_get_agent_status_writes_nothing_even_for_the_owner`|`keep`|GET de agent-status não faz commit.|
|`test_owner_connect_returns_the_qr_code`|`keep`|Connect devolve o QR code e status connecting.|
|`test_owner_connect_on_an_already_connected_instance_has_no_qr`|`keep`|Instance já conectada volta sem QR.|
|`test_evolution_errors_map_to_http_status (×3 casos)`|`keep`|Erro da Evolution vira 404, 401 ou 502.|
|`test_owner_logout_disconnects_in_evolution`|`keep`|Logout desconecta na Evolution.|
|`test_delete_when_evolution_no_longer_has_it_still_deactivates_locally`|`keep`|Evolution 404 no delete ainda desativa local.|
|`test_delete_with_an_evolution_failure_keeps_the_local_instance`|`keep`|Falha 500 da Evolution mantém a Instance ativa.|
|`test_agent_binding_unbind_survives_later_requests`|`redundant`|Mesmo unbind com `agent_id` None e `agent_enabled` False: `tests/api/test_instance_agent_status.py::test_patch_agent_binding_unbinds_agent_and_disables_auto_reply`. **Removido na #53.**|
|`test_socket_subscription_follows_the_owner_rule`|`keep`|Regra de dono também vale na assinatura Socket.IO.|

#### `tests/api/test_main.py`
2 testes: 1 keep, 1 wording.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_health_check`|`keep`|Probe de saúde responde 200 e healthy|
|`test_root`|`wording`|Fixa o texto literal `"Neuralilux API"` da mensagem da raiz; nada além de 200 é contrato **Mantido na #53:** é o único teste que chama `GET /`; apagá-lo tira a rota `root` de `app/main.py` da cobertura. Fortalecido: a asserção do texto literal virou `version` não vazio.|

#### `tests/api/test_menu_inventory.py`
6 testes: 6 keep (serviço sem chamador em `app/` fora do próprio módulo, mas cada teste cobre uma regra real da função).

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_get_menu_item`|`keep`|Busca por ID devolve o item certo|
|`test_get_menu_item_not_found`|`keep`|ID inexistente devolve None, sem erro|
|`test_get_menu_items_by_company`|`keep`|Filtro `only_available` alterna 3 vs 4 itens|
|`test_list_menu_items`|`keep`|Paginação skip/limit: página 1 com 3, página 2 com 2|
|`test_soft_delete_menu_item`|`keep`|Baixa lógica mantém o item com is_available False|
|`test_soft_delete_menu_item_not_found`|`keep`|Baixa de item inexistente devolve False|

#### `tests/api/test_menu_management_endpoints.py`
9 testes: 8 keep, 1 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_get_menu_creates_manual_catalog_when_missing`|`keep`|GET cria catálogo manual ativo quando não existe|
|`test_create_category_for_active_catalog`|`keep`|Categoria nasce no catálogo ativo da Company|
|`test_create_and_update_item_with_custom_attributes`|`keep`|Criação e PATCH persistem sku, estoque e atributos|
|`test_editing_imported_catalog_marks_it_manual_and_delete_category_removes_items`|`keep`|Editar catálogo importado vira manual; delete remove itens|
|`test_create_item_with_sku_and_stock`|`redundant`|POST de item com `sku`/`stock_quantity` e mesmas asserções já feitos em `tests/api/test_menu_management_endpoints.py::test_create_and_update_item_with_custom_attributes` (criação) e `::test_list_menu_includes_sku_and_stock` **Removido na #53.**|
|`test_duplicate_sku_rejected`|`keep`|SKU duplicado na criação responde 409|
|`test_update_sku_with_uniqueness_validation`|`keep`|PATCH para SKU já usado responde 409|
|`test_stock_quantity_validation_on_delete`|`keep`|Categoria com item em estoque não pode ser apagada (400)|
|`test_list_menu_includes_sku_and_stock`|`keep`|Snapshot GET expõe sku e estoque dos itens|

#### `tests/api/test_order_refunds.py`
9 testes: 8 keep, 1 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_company_sees_only_its_own_open_refunds`|`keep`|Lista só estornos abertos da própria Company|
|`test_marking_a_refund_as_done_removes_it_from_the_pending_list`|`keep`|Baixa grava refunded_at e some da lista|
|`test_marking_the_same_refund_twice_is_idempotent`|`keep`|Segunda baixa não regrava refunded_at|
|`test_already_refunded_record_still_answers_200`|`redundant`|Baixar registro já `refunded` e receber 200/`refunded` é a 2ª chamada de `tests/api/test_order_refunds.py::test_marking_the_same_refund_twice_is_idempotent` **Removido na #53.**|
|`test_unpaid_pix_can_be_dismissed_after_checking_the_bank`|`keep`|Pix `verify` pode ser descartado, idempotente|
|`test_contradicting_a_closed_refund_is_409_and_keeps_the_state`|`keep`|Descartar estorno já pago dá 409 sem mudar estado|
|`test_refunds_require_a_token`|`keep`|Sem token: 401 em todas as rotas, estado intacto|
|`test_refund_of_another_company_is_404_and_untouched`|`keep`|Estorno de outra Company dá 404 e não muda|
|`test_record_without_pending_refund_cannot_be_marked`|`keep`|Registro sem estorno pendente não pode ser baixado (404)|

#### `tests/api/test_order_status.py`
20 testes: 19 keep, 1 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_panel_lists_only_active_confirmed_orders_by_default`|`keep`|Filtro padrão exclui entregue, cancelado, montagem, abandonado|
|`test_panel_row_carries_what_the_company_needs_to_act`|`keep`|Linha traz itens, total e transições permitidas por status|
|`test_order_being_altered_is_shown_as_such_and_cannot_be_moved`|`keep`|Pedido em alteração sinalizado e sem transições|
|`test_panel_lists_newest_first_and_honours_limit`|`redundant`|Ordem `A-4, A-3` e `limit` já cobertos por `tests/api/test_order_status.py::test_offset_and_limit_page_through_the_filtered_list_with_the_total` e `::test_status_filter_splits_active_from_finished_and_all_lists_everything` **Removido na #53.**|
|`test_panel_flags_orders_with_a_pix_to_refund`|`keep`|Pedido com Pix a estornar expõe refund_status pending|
|`test_status_filter_splits_active_from_finished_and_all_lists_everything`|`keep`|Filtros active/done/all com ordem e total exatos|
|`test_unknown_status_filter_is_422`|`keep`|Filtro de status inválido é rejeitado com 422|
|`test_offset_and_limit_page_through_the_filtered_list_with_the_total`|`keep`|Paginação, offset além do fim e offset negativo|
|`test_old_received_order_is_still_listed_behind_many_newer_delivered_ones`|`keep`|Filtro antes da paginação: pedido antigo não some|
|`test_listing_runs_the_same_number_of_queries_however_many_orders_there_are`|`keep`|Guarda contra N+1 na listagem de estornos|
|`test_panel_requires_a_token`|`keep`|Sem token: 401 na lista e na transição|
|`test_company_walks_an_order_to_delivered_and_the_contact_hears_each_step`|`keep`|Fluxo completo com aviso ao Contact a cada passo|
|`test_invalid_transitions_are_refused_without_side_effects` (×10 casos)|`keep`|Transição inválida dá 409 sem mensagem nem mudança|
|`test_order_being_altered_refuses_every_move`|`keep`|Pedido em alteração recusa qualquer movimento (409)|
|`test_unknown_target_status_is_rejected`|`keep`|Status alvo desconhecido ou interno dá 422|
|`test_order_of_another_company_is_404_and_untouched`|`keep`|Pedido de outra Company: 404 e intacto|
|`test_order_that_does_not_exist_is_404`|`keep`|Pedido inexistente responde 404|
|`test_failure_to_notify_keeps_the_new_status_and_is_reported`|`keep`|Falha no aviso mantém status e reporta erro|
|`test_company_cancelling_a_dinheiro_order_tells_the_contact_without_mentioning_refund`|`keep`|Cancelar pedido em dinheiro não menciona estorno|
|`test_company_cancelling_a_pix_order_flags_the_refund_like_the_contacts_cancel` (×2 casos)|`keep`|Cancelar pedido Pix marca estorno pending ou verify|

#### `tests/api/test_order_status_race.py`
3 testes: 3 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_two_company_moves_from_the_same_read_state_only_one_wins`|`keep`|Transição condicional: só um movimento vence|
|`test_company_cancel_loses_nothing_when_the_contact_cancelled_first`|`keep`|Contact cancela antes: sem aviso falso de preparo|
|`test_contact_cancel_loses_when_the_company_started_preparing_first`|`keep`|Company prepara antes: cancelamento do Contact recusado|

#### `tests/api/test_register_company.py`
5 testes: 5 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_anonymous_register_with_company_is_403_and_creates_nothing`|`keep`|Anônimo não escolhe Company e nada é criado|
|`test_regular_user_cannot_register_into_a_company`|`keep`|Usuário comum não registra em Company (403)|
|`test_superuser_registers_user_into_a_company`|`keep`|Superuser registra usuário em Company (201)|
|`test_anonymous_register_without_company_still_works`|`keep`|Registro anônimo sem Company continua funcionando|
|`test_invalid_token_on_register_is_401`|`keep`|Token inválido não vira registro anônimo (401)|

#### `tests/api/test_tickets_scoping.py`
10 testes: 10 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_list_is_filtered_per_user`|`keep`|Lista de tickets restrita às Instances do usuário|
|`test_superuser_lists_all`|`keep`|Superuser vê tickets de todas as Companies|
|`test_get_out_of_scope_ticket_is_404`|`keep`|GET de ticket alheio dá 404; superuser acessa|
|`test_patch_out_of_scope_ticket_is_404_and_unchanged`|`keep`|PATCH de ticket alheio dá 404 sem alterar|
|`test_assign_out_of_scope_ticket_is_404`|`keep`|Atribuir ticket alheio dá 404|
|`test_assign_accepts_user_of_the_instance_company`|`keep`|Atribuição a colega da Company vira in_progress|
|`test_assign_refuses_user_of_another_company`|`keep`|Atribuir a usuário de outra Company dá 403|
|`test_patch_assigned_to_applies_the_same_company_rule`|`keep`|PATCH assigned_to aplica a mesma regra de Company|
|`test_superuser_may_assign_across_companies`|`keep`|Superuser atribui entre Companies (precedência)|
|`test_assign_on_an_instance_without_company_is_refused_to_regular_users`|`keep`|Instance sem Company recusa atribuição a usuário comum|

#### `tests/api/test_webhook_auth.py`
12 testes: 12 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_post_without_token_is_unauthorized_and_not_published` (×2 casos)|`keep`|Sem token: 401 e nada publicado, nas duas rotas|
|`test_post_with_wrong_token_is_unauthorized` (×4 casos)|`keep`|Token vazio, errado, maior ou menor: 401|
|`test_post_with_non_ascii_token_is_unauthorized_not_a_server_error`|`keep`|Token não-ASCII dá 401, não 500|
|`test_post_with_correct_token_is_published`|`keep`|Token correto publica o evento do payload|
|`test_event_path_with_correct_token_is_published`|`keep`|Rota por evento deriva o nome do evento do path|
|`test_event_suffix_glued_to_the_token_is_accepted_and_used_as_event`|`keep`|WEBHOOK_BY_EVENTS: sufixo colado ao token vira evento|
|`test_payload_event_wins_over_the_suffix_glued_to_the_token`|`keep`|Precedência: evento do payload vence o sufixo|
|`test_suffix_does_not_rescue_a_wrong_secret` (×3 casos)|`keep`|Sufixo não salva segredo errado (401)|
|`test_token_followed_by_a_bare_slash_is_accepted_without_event`|`keep`|Token com `/` solto aceito sem evento inventado|
|`test_unconfigured_token_rejects_every_call_even_with_an_empty_token`|`keep`|Token não configurado recusa tudo, inclusive vazio|
|`test_health_probe_also_requires_the_token`|`keep`|Probe do webhook também exige token|
|`test_settings_do_not_ship_secrets_or_debug_on_by_default`|`keep`|Defaults não embutem API key, token nem DEBUG ligado|

#### `tests/core/test_access_log_redaction.py`
3 testes: 2 keep, 1 redundant.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_token_value_is_masked_in_the_webhook_path`|`keep`|Token do webhook nunca vaza no access log; preserva `x=1`.|
|`test_other_paths_are_left_untouched`|`keep`|Fronteira: `token_type=` não é mascarado.|
|`test_records_with_unexpected_args_pass_through`|`redundant`|Apesar do nome, usa tupla de `str` sem `token=` (não exercita args não-tuple/não-str); mesmo caminho e asserção de `tests/core/test_access_log_redaction.py::test_other_paths_are_left_untouched`. **Removido na #53.**|

#### `tests/core/test_config_secret_key.py`
6 testes: 6 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_default_secret_key_is_refused_outside_development` (×2 casos)|`keep`|Produção/staging recusam SECRET_KEY padrão.|
|`test_example_env_secret_key_is_also_refused_in_production`|`keep`|Pega validação por igualdade em vez de prefixo (chave do .env de exemplo).|
|`test_default_secret_key_is_allowed_in_development`|`keep`|Fronteira: dev continua subindo com chave de exemplo.|
|`test_real_secret_key_is_accepted_in_production`|`keep`|Evita bloqueio indevido de config válida em produção.|
|`test_empty_or_example_webhook_token_is_refused_outside_development` (×6 casos)|`keep`|Webhook token vazio/exemplo recusado fora de dev.|
|`test_empty_webhook_token_is_allowed_in_development`|`keep`|Dev aceita token vazio (fronteira do validator).|

#### `tests/models/test_payment_record_model.py`
4 testes: 4 wiring.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`TestPaymentRecordModel::test_create_payment_record`|`wiring`|Só relê os campos que acabou de gravar (`amount == 100.00`, `pix_key`, `status == "pending"`); nenhuma regra/constraint/default de negócio, e o caminho é exercido por `tests/packs/test_pack_pix.py`. **Removido na #53.**|
|`TestPaymentRecordModel::test_payment_record_paid_status`|`wiring`|`assert payment.status == "paid"` e `paid_at is not None` apenas ecoam o que foi passado ao construtor. **Removido na #53.**|
|`TestPaymentRecordModel::test_payment_record_relationships`|`wiring`|Só confere `payment.order.id == order.id` / `payment.conversation.id`; esses relationships não são usados em `app/`. **Removido na #53.**|
|`TestPaymentRecordModel::test_payment_record_expired_status`|`wiring`|`assert payment.status == "expired"` ecoa o valor gravado; não testa transição nem o índice único. **Removido na #53.**|

#### `tests/models/test_ticket_model.py`
4 testes: 4 wiring.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`TestTicketModel::test_create_ticket`|`wiring`|Copia 8 campos e relê (`agent_type == "sac"`, `status == "open"`); sem regra de negócio, Ticket já é exercido em `tests/handoff/*`. **Removido na #53.**|
|`TestTicketModel::test_ticket_with_assigned_user`|`wiring`|`ticket.assigned_to == user.id` e `status == "in_progress"` apenas ecoam a entrada. **Removido na #53.**|
|`TestTicketModel::test_ticket_sales_agent_type`|`wiring`|`assert ticket.agent_type == "sales"` ecoa o valor passado ao construtor. **Removido na #53.**|
|`TestTicketModel::test_ticket_relationships`|`wiring`|Só confere `ticket.conversation.id == conversation.id` (e instance/contact); mapeamento ORM sem comportamento. **Removido na #53.**|

### Área 2: whatsapp / realtime

#### `tests/realtime/test_realtime_event_bus.py`
2 testes: 2 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_publish_after_the_previous_loop_was_closed_uses_a_fresh_client`|`keep`|Regressão real: cliente Redis preso a loop fechado.|
|`test_publishes_in_the_same_loop_share_one_client`|`keep`|Evita criar um cliente Redis por publish.|

#### `tests/realtime/test_socket_access.py`
7 testes: 7 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_join_conversation_follows_the_instance_owner` (×4 casos)|`keep`|Só dono/superusuário entram na sala da Conversation.|
|`test_join_conversation_of_an_unknown_instance_is_denied`|`keep`|Instance inexistente nega join sem sala.|
|`test_send_message_follows_the_instance_owner` (×4 casos)|`keep`|Só dono/superusuário enviam; negado não chama Evolution.|
|`test_send_message_accepts_the_remote_jid_as_conversation_reference`|`keep`|Contrato: conversationId pode ser o remote_jid.|
|`test_send_message_refuses_a_conversation_of_another_instance_even_for_the_owner`|`keep`|Bloqueia IDOR: Conversation/JID de outra Instance.|
|`test_superuser_cannot_send_to_a_conversation_outside_the_named_instance`|`keep`|Superusuário não burla o escopo da Instance nomeada.|
|`test_leaving_never_needs_access`|`keep`|Sair da sala funciona e remove a sala.|

#### `tests/realtime/test_socket_thinking_events.py`
5 testes: 3 keep, 2 redundant. #54 removeu os 2 `redundant`; restam 3.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_thinking_reaches_the_conversation_room_and_the_instance_room`|`keep`|Roteamento de thinking para as duas salas; único teste dessa ponta do socket.|
|`test_tool_call_reaches_the_client_as_started_then_completed_with_one_trace`|`keep`|Normalização camelCase de tool_event e traceId único no socket.|
|`test_failed_tool_reaches_the_client_with_its_error`|`keep`|Fase `failed` e `error` chegam ao cliente (camada socket).|
|`test_handoff_request_reaches_both_rooms_with_ticket_and_reason`|`redundant`|Mesmas salas e `ticketId`/`reason` no socket que `tests/agent/test_handoff_socket.py::test_handoff_event_from_the_tool_reaches_instance_and_conversation_rooms`, que parte da Tool real; aqui só passa por `publish_handoff_requested`, helper sem chamador em `app/`. **Removido (#54).**|
|`test_event_without_instance_is_dropped`|`redundant`|O descarte por falta de `instance_name` é o mesmo `return` inicial de `emit_realtime_event` coberto por `tests/agent/test_handoff_socket.py::test_handoff_event_without_instance_is_dropped_like_other_events`. **Removido (#54).**|

#### `tests/whatsapp/test_debounce_context.py`
6 testes: 6 keep.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_text_media_text_in_one_window_is_one_turn_with_exactly_the_two_texts`|`keep`|Rajada texto+mídia+texto: um Turn, mídia respondida uma vez|
|`test_burst_across_a_session_boundary_is_not_duplicated_and_abandons_the_order_once`|`keep`|Rajada na virada de sessão: sem duplicar, Order abandonado uma vez|
|`test_follower_stored_when_the_window_closes_joins_the_group_and_is_answered_once`|`keep`|Corrida: seguidora gravada após fechar a janela entra no grupo|
|`test_transfer_requested_in_a_burst_transfers_once_and_later_messages_do_not_run_the_agent`|`keep`|Handoff em rajada: um Ticket, Message tardia não roda o Agent|
|`test_attendant_taking_over_during_the_window_prevents_the_turn`|`keep`|Attendant assume na janela: nenhum Turn, Messages gravadas|
|`test_without_grouping_each_message_gets_its_own_turn_and_the_queued_ones_stay_out_of_its_history`|`keep`|Sem janela: Turns em série, fila fora do histórico do Turn|

#### `tests/whatsapp/test_evolution_realtime_service.py`
1 teste: 1 keep.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_forward_event_publishes_webhook_payload`|`keep`|Injeta `event` e `source` que o websocket não envia|

#### `tests/whatsapp/test_evolution_service.py`
29 testes: 15 keep, 7 redundant, 4 wiring, 2 wording, 1 stub. #54 removeu os 14 candidatos; restam 15.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`TestEvolutionAPIError::test_message_and_code`|`wiring`|Só relê atributos que o `__init__` acabou de atribuir (`err.message`, `err.status_code`, `str(err)`) **Removido (#54).**|
|`TestEvolutionAPIError::test_default_status_code`|`wording`|Fixa o default incidental `status_code == 500` do construtor **Removido (#54).**|
|`TestEvolutionAPIService::test_init_sets_base_url_and_headers`|`stub`|Só `base_url is not None` e chaves presentes em `headers`, sem checar valor **Removido (#54).**|
|`TestFetchChats::test_uses_post_method`|`redundant`|Rota respx já é `post`; `method == "POST"` é tautologia. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchChats::test_sends_empty_json_body` **Removido (#54).**|
|`TestFetchChats::test_correct_url`|`redundant`|URL já é exigida pela rota respx de todo teste da classe. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchChats::test_sends_empty_json_body` **Removido (#54).**|
|`TestFetchChats::test_sends_empty_json_body`|`keep`|Evolution v2.3.7 exige POST com corpo `{}`|
|`TestFetchChats::test_sends_apikey_header`|`keep`|Autenticação: header `apikey` chega à Evolution|
|`TestFetchChats::test_returns_chat_list`|`wiring`|`result == chats`: só repassa o JSON do mock **Removido (#54).**|
|`TestFetchChats::test_raises_on_404`|`keep`|HTTP 404 vira `EvolutionAPIError` com status|
|`TestFetchMessages::test_uses_post_method`|`redundant`|Rota respx já é `post`. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchMessages::test_sends_correct_payload` **Removido (#54).**|
|`TestFetchMessages::test_correct_url`|`redundant`|URL já é exigida pela rota respx. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchMessages::test_sends_correct_payload` **Removido (#54).**|
|`TestFetchMessages::test_sends_correct_payload`|`keep`|`where.key.remoteJid` e `limit` vindos de `offset`|
|`TestFetchMessages::test_default_offset`|`wording`|Fixa o default incidental `limit == 20` **Removido (#54).**|
|`TestFetchMessages::test_returns_messages`|`wiring`|`result == response_data`: só repassa o JSON do mock **Removido (#54).**|
|`TestFetchContacts::test_uses_post_method`|`redundant`|Rota respx já é `post`. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchContacts::test_sends_empty_json_body` **Removido (#54).**|
|`TestFetchContacts::test_correct_url`|`redundant`|URL já é exigida pela rota respx. Equivalente: `tests/whatsapp/test_evolution_service.py::TestFetchContacts::test_sends_empty_json_body` **Removido (#54).**|
|`TestFetchContacts::test_sends_empty_json_body`|`keep`|Evolution v2.3.7 exige POST com corpo `{}`|
|`TestFetchContacts::test_returns_contacts`|`wiring`|`result == contacts`: só repassa o JSON do mock **Removido (#54).**|
|`TestSendTextMessage::test_uses_post_method`|`redundant`|Rota respx já é `post`. Equivalente: `tests/whatsapp/test_evolution_service.py::TestSendTextMessage::test_strips_jid_suffix` **Removido (#54).**|
|`TestSendTextMessage::test_strips_jid_suffix`|`keep`|`number` vai só com dígitos, sem `@s.whatsapp.net`|
|`TestSendTextMessage::test_sends_text_and_options`|`keep`|Texto enviado chega no payload (delay/presence junto)|
|`TestSendTextMessage::test_raises_on_500`|`keep`|HTTP 500 no envio vira `EvolutionAPIError`|
|`TestCreateInstance::test_sends_integration_field`|`keep`|Evolution v2 exige `integration` na criação|
|`TestSendPresence::test_posts_composing_with_the_number_and_delay`|`keep`|Corpo exato exigido pela Evolution: number, presence, delay|
|`TestSendPresence::test_http_error_raises_evolution_error`|`keep`|Erro HTTP na presença continua levantando|
|`TestSendPresence::test_rejects_a_jid_without_digits`|`keep`|JID sem dígitos (`status@broadcast`) é recusado|
|`TestSendPresence::test_uses_a_short_timeout_independent_of_the_delay`|`keep`|Timeout de leitura curto, independente do delay|
|`TestSendPresence::test_read_timeout_while_evolution_holds_the_delay_counts_as_accepted`|`keep`|ReadTimeout durante o delay vale como aceito|
|`TestSendPresence::test_connection_refused_still_raises`|`keep`|ConnectError não é engolido como timeout|

#### `tests/whatsapp/test_handoff_exit_consumer.py`
6 testes: 6 keep.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_agent_stays_silent_during_handoff_and_answers_after_release`|`keep`|Agent mudo em Handoff, volta após `release`|
|`test_overdue_handoff_expires_on_the_next_message_and_agent_answers`|`keep`|Timeout de 4h expira Ticket e o Agent responde|
|`test_attendant_message_from_the_phone_postpones_the_timeout`|`keep`|`fromMe` do Attendant adia o timeout do Handoff|
|`test_agent_reply_echo_with_a_known_id_does_not_restart_the_attendant_clock`|`keep`|Eco da resposta do Agent não conta como Attendant|
|`test_echo_of_an_agent_reply_sent_without_id_does_not_restart_the_attendant_clock`|`keep`|Eco sem id também não reinicia o relógio|
|`test_attendant_message_with_the_same_text_as_a_past_reply_still_counts`|`keep`|Eco sem id vale uma vez; segundo igual é Attendant|

#### `tests/whatsapp/test_history_sync.py`
12 testes: 12 keep.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_sync_imports_one_to_one_lid_and_group_with_names`|`keep`|Importa 1:1, @lid e grupo; nomes; ignora broadcast/reação|
|`test_sync_stores_direction_sender_timestamp_and_status`|`keep`|Direção, remetente, timestamp e status das Messages importadas|
|`test_sync_sets_last_message_and_unread_from_find_chats`|`keep`|Última Message e unread vindos do findChats|
|`test_second_run_creates_nothing_and_keeps_existing_rows`|`keep`|Reimportação idempotente, sem sobrescrever linhas|
|`test_sync_never_calls_the_agent_or_rolls_a_session`|`keep`|Importação nunca aciona Agent nem abre sessão|
|`test_sync_does_not_move_last_message_backwards`|`keep`|Histórico antigo não regride a última Message|
|`test_sync_survives_groups_and_contacts_failing`|`keep`|Falha em grupos/contatos não derruba a importação|
|`test_resync_does_not_overwrite_unread_of_existing_conversations`|`keep`|Reimportação não reabre unread lido pelo atendente|
|`test_message_id_inserted_by_another_process_before_commit_does_not_lose_the_batch`|`keep`|Corrida com webhook não perde o lote|
|`test_sync_yields_to_the_event_loop_between_batches`|`keep`|Importação cede o event loop entre lotes|
|`test_postgres_advisory_lock_is_held_during_the_import_and_released_after`|`keep`|Advisory lock tomado antes e liberado depois|
|`test_sync_raises_when_another_process_holds_the_lock`|`keep`|Sem o lock: `SyncAlreadyRunning`, sem importar nem unlock|

#### `tests/whatsapp/test_history_sync_trigger.py`
6 testes: 5 keep, 1 wording. #54 não removeu: o teste `wording` foi reforçado e virou `keep`; restam 6.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_history_events_schedule_one_sync (×4 casos)`|`keep`|Cada evento de histórico agenda uma importação|
|`test_connection_open_schedules_sync_but_close_does_not`|`keep`|Só `connection.update` aberto dispara importação|
|`test_second_event_is_ignored_while_a_sync_runs_and_allowed_after`|`keep`|No máximo uma importação por Instance, liberada depois|
|`test_sync_for_unknown_instance_is_ignored`|`keep`|Instance desconhecida não dispara importação|
|`test_failed_sync_is_logged_and_frees_the_instance`|`keep`|Falha da importação libera a Instance para nova tentativa|
|`test_worker_skips_silently_when_another_process_is_importing`|`wording`|Só `consumer._syncing == set()` (atributo interno); passa igual se `SyncAlreadyRunning` cair no `except Exception`, já coberto pelo teste de falha **Mantido (#54):** reforçado e renomeado para `test_worker_skips_with_an_info_log_when_another_process_is_importing`; agora afirma o log informativo, a ausência de `logger.exception` e a Instance liberada. Passa a `keep`.|

#### `tests/whatsapp/test_message_queue_service.py`
7 testes: 7 keep.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_successful_callback_acks_the_message_with_the_decoded_payload`|`keep`|Sucesso: payload decodificado e ack|
|`test_invalid_json_is_rejected_without_requeue_and_never_reaches_the_callback`|`keep`|JSON inválido: reject sem requeue, callback não roda|
|`test_first_failure_requeues_the_message`|`keep`|Primeira falha devolve à fila|
|`test_failure_on_redelivery_drops_the_message_instead_of_looping`|`keep`|Falha na reentrega descarta (sem loop quente)|
|`test_redelivered_message_that_succeeds_is_acked`|`keep`|Reentrega bem-sucedida não é descartada|
|`test_deliveries_run_concurrently_in_one_event_loop`|`keep`|Entregas concorrentes no mesmo loop|
|`test_stop_waits_for_in_flight_deliveries_before_returning`|`keep`|Shutdown espera entregas em voo|

#### `tests/whatsapp/test_realtime_bridge.py`
5 testes: 4 keep, 1 redundant. #54 removeu o `redundant`; restam 4.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_save_message_to_database_handles_evolution_event_shape_and_publishes_realtime`|`keep`|Contact, Conversation, Message e evento ao vivo no shape do frontend|
|`test_update_message_status_normalizes_and_publishes_realtime_event`|`keep`|Status `READ` normalizado, gravado e publicado|
|`test_connection_update_normalizes_state_and_publishes_realtime_event`|`keep`|Estado `open` vira `connected` e é publicado|
|`test_save_message_to_database_does_not_trigger_agent_when_instance_is_disabled`|`redundant`|Mesma asserção (`agent_enabled=False` ⇒ sem Turn nem envio). Equivalente: `tests/whatsapp/test_whatsapp_consumer.py::test_disabled_agent_does_not_answer` **Removido (#54).**|
|`test_save_message_to_database_triggers_agent_when_instance_is_enabled`|`keep`|Turn, envio da resposta e Summary disparados|

#### `tests/whatsapp/test_recap_delivery_consumer.py`
6 testes: 6 keep.
| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_recap_delivered_then_confirmed_closes_the_order`|`keep`|Recap entregue + confirmação fecha o Order|
|`test_turn_that_fails_after_recapitular_does_not_leave_a_valid_recap`|`keep`|Falha do Gateway invalida o Recap|
|`test_turn_without_reply_does_not_leave_a_valid_recap`|`keep`|Turn sem texto invalida o Recap|
|`test_send_failure_does_not_leave_a_valid_recap`|`keep`|Falha no envio invalida o Recap|
|`test_reply_dropped_by_handoff_does_not_leave_a_valid_recap`|`keep`|Resposta descartada por Handoff invalida o Recap|
|`test_confirmation_sent_before_the_recap_reached_the_contact_does_not_close`|`keep`|Confirmação anterior à entrega do Recap não fecha|

#### `tests/whatsapp/test_status_notice_echo.py`
3 testes: 3 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_status_notice_echo_neither_reopens_the_agent_nor_resets_the_handoff_clock (×2 casos)`|`keep`|Eco do aviso não reabre Agent nem move relógio do Handoff|
|`test_status_notice_echo_is_deduplicated (×2 casos)`|`keep`|Eco repetido do aviso gera uma só Message|
|`test_attendant_message_still_counts_while_a_notice_without_id_waits_for_its_echo`|`keep`|Texto de Attendant ainda conta como atividade|

#### `tests/whatsapp/test_turn_batcher.py`
12 testes: 12 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_messages_inside_the_window_become_one_turn_with_all_of_them`|`keep`|Agrupa Messages da janela em um Turn só|
|`test_a_message_after_the_pause_starts_a_new_turn`|`keep`|Fronteira da janela: pausa abre novo Turn|
|`test_followers_return_at_once_and_only_the_first_submit_waits_for_the_turn`|`keep`|Só a líder espera o Turn; seguidoras voltam já|
|`test_message_during_a_turn_waits_for_the_next_turn_without_overlap_or_loss`|`keep`|Sem Turn sobreposto nem perda durante Turn em curso|
|`test_different_conversations_run_in_parallel`|`keep`|Conversations distintas não se serializam|
|`test_failing_turn_does_not_lose_the_messages_that_arrived_meanwhile`|`keep`|Turn que falha não perde Messages enfileiradas|
|`test_state_is_released_when_idle`|`keep`|Sem vazamento de estado após ocioso|
|`test_grouped_turn_carries_the_timestamp_of_the_oldest_message`|`keep`|Grupo usa o timestamp mais antigo, mesmo fora de ordem|
|`test_next_turn_starts_its_own_oldest_timestamp`|`keep`|Timestamp do grupo não vaza para o Turn seguinte|
|`test_message_stored_but_not_yet_submitted_joins_the_group_and_is_never_in_two_turns`|`keep`|Corrida: Message gravada entra no grupo, uma vez só|
|`test_released_hold_without_submit_does_not_block_the_leader`|`keep`|Hold solto (ex.: Handoff) não trava a líder|
|`test_zero_window_runs_one_turn_per_message_in_arrival_order`|`keep`|Janela zero: um Turn por Message, em ordem, sem sobrepor|

#### `tests/whatsapp/test_typing_refresh.py`
2 testes: 2 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_presence_is_sent_at_0_20_and_40_seconds_of_a_45_second_turn_then_stops`|`keep`|Renovação periódica do "digitando" e parada ao fim do Turn|
|`test_presence_failure_ends_the_loop_without_raising`|`keep`|Falha de presença não derruba o Turn nem insiste|

#### `tests/whatsapp/test_whatsapp_actions.py`
24 testes (o grep `def test_` contava 25 porque casava também a fixture `test_instance`): 10 keep, 12 stub, 2 wiring. Decisão de #54: **mantido como e2e documentado e funcionando**, só leitura. Os 14 `stub`/`wiring` foram removidos; restam os 10 `keep`. O arquivo não cria nem apaga instância (o fixture que criava `integration-test-instance` saiu), não envia mensagem (o único `send_text_message` vai a uma instância inexistente e tem de falhar) e lê a instância real `Macedos` (sobrescrevível por `E2E_EVOLUTION_INSTANCE`). Rodado com `RUN_E2E=1` contra a Evolution local: 10 passed. Como rodar: docstring do arquivo e `docs/setup.md`.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`TestListChats::test_fetch_chats_returns_list`|`keep`|Contrato real: `findChats` devolve lista|
|`TestListChats::test_fetch_chats_with_valid_instance`|`stub`|Só `assert result is not None`; já coberto pelo `returns_list` **Removido (#54).**|
|`TestListChats::test_fetch_chats_invalid_instance_raises_error`|`keep`|Instância inexistente vira `EvolutionAPIError` real|
|`TestListChats::test_fetch_chats_response_structure`|`stub`|`... or isinstance(chat, dict)` é tautologia; vazio se não há chats **Removido (#54).**|
|`TestListContacts::test_fetch_contacts_returns_list`|`keep`|Contrato real: `findContacts` devolve lista|
|`TestListContacts::test_fetch_contacts_with_valid_instance`|`stub`|Só `assert result is not None`; já coberto pelo `returns_list` **Removido (#54).**|
|`TestListContacts::test_fetch_contacts_invalid_instance_raises_error`|`keep`|Instância inexistente vira `EvolutionAPIError` real|
|`TestListContacts::test_fetch_contacts_response_structure`|`stub`|`isinstance(contact, dict)` só se houver contato; instância nova é vazia **Removido (#54).**|
|`TestReadMessages::test_fetch_messages_returns_dict`|`keep`|Contrato real: `findMessages` devolve dict|
|`TestReadMessages::test_fetch_messages_with_pagination`|`stub`|Só `assert result is not None`; `page` é ignorado pelo client **Removido (#54).**|
|`TestReadMessages::test_fetch_messages_default_offset`|`stub`|Docstring fala em offset 20 mas só assere `is not None` (payload já em `test_evolution_service.py::TestFetchMessages::test_default_offset`) **Removido (#54).**|
|`TestReadMessages::test_fetch_messages_invalid_instance_raises_error`|`keep`|Instância inexistente vira `EvolutionAPIError` real|
|`TestConnectionStatus::test_get_instance_status_returns_dict`|`keep`|Contrato real: `connectionState` devolve dict|
|`TestConnectionStatus::test_get_instance_status_contains_state`|`keep`|Resposta traz `instance` ou `state`|
|`TestConnectionStatus::test_get_instance_status_valid_states`|`stub`|`state in valid_states or isinstance(state, str)` é tautologia **Removido (#54).**|
|`TestConnectionStatus::test_get_instance_status_invalid_instance_raises_error`|`keep`|Instância inexistente vira `EvolutionAPIError` real|
|`TestSendMessage::test_send_text_message_accepts_request`|`stub`|Engole status 500 (caso normal sem WhatsApp conectado); quase nunca assere nada **Removido (#54).**|
|`TestSendMessage::test_send_text_message_invalid_instance_raises_error`|`keep`|Envio a instância inexistente levanta erro real|
|`TestEvolutionAPIConnectivity::test_api_is_reachable`|`stub`|Só falha se a Evolution estiver fora do ar; testa ambiente, não código **Removido (#54).**|
|`TestEvolutionAPIConnectivity::test_api_base_url_configured`|`stub`|`"localhost:8081" in url or "http" in url` é tautologia **Removido (#54).**|
|`TestEvolutionAPIConnectivity::test_api_key_configured`|`wiring`|Confere só que `settings.EVOLUTION_API_KEY` chegou a `api_key` **Removido (#54).**|
|`TestEvolutionAPIConnectivity::test_headers_contain_apikey`|`wiring`|Cópia `api_key`→`headers["apikey"]`; header já enviado em `test_evolution_service.py::TestFetchChats::test_sends_apikey_header` **Removido (#54).**|
|`TestInstanceLifecycle::test_create_and_delete_instance`|`stub`|Só `is not None` nos dois retornos; erro HTTP já levantaria sozinho **Removido (#54).**|
|`TestInstanceLifecycle::test_create_duplicate_instance_handled`|`stub`|Passa se o segundo create tiver sucesso ou falhar com 4 códigos; sem asserção sobre o tratamento **Removido (#54).**|

#### `tests/whatsapp/test_whatsapp_consumer.py`
20 testes: 20 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_unknown_instance_is_discarded_and_nothing_is_created`|`keep`|Instance desconhecida não cria Message/Contact/Turn|
|`test_connection_update_for_unknown_instance_does_not_create_one`|`keep`|`connection.update` não cria Instance desconhecida|
|`test_broadcast_messages_never_reach_the_agent_or_the_database (×2 casos)`|`keep`|Broadcast/status nunca chega ao Agent nem ao banco|
|`test_from_me_message_is_stored_but_the_agent_stays_silent`|`keep`|`fromMe` é gravada e o Agent não responde|
|`test_message_older_than_five_minutes_before_consumer_start_is_stored_but_not_answered`|`keep`|Backlog antigo (5min30) gravado sem responder|
|`test_message_within_five_minutes_of_consumer_start_is_answered`|`keep`|Fronteira do backlog: 4min ainda é respondida|
|`test_lid_jid_is_resolved_to_the_real_number_and_answered_there (×2 casos)`|`keep`|`@lid` vira número real e a resposta vai a ele|
|`test_lid_without_a_real_number_is_stored_but_not_answered`|`keep`|`@lid` sem número real não recebe resposta|
|`test_media_without_text_gets_the_fixed_reply_without_calling_the_model (×5 casos)`|`keep`|Mídia sem texto recebe resposta fixa sem chamar modelo|
|`test_media_with_a_caption_is_handled_as_text`|`keep`|Legenda de mídia vai ao Agent como texto|
|`test_media_reply_is_not_sent_during_handoff`|`keep`|Resposta fixa de mídia calada em Handoff|
|`test_bot_reply_is_stored_as_from_me_with_the_evolution_id`|`keep`|Reply gravada com id Evolution, preview e unread|
|`test_webhook_echo_of_the_reply_is_deduplicated_and_does_not_trigger_the_agent`|`keep`|Eco da reply não duplica nem aciona o Agent|
|`test_redelivered_incoming_message_is_answered_once`|`keep`|Webhook reentregue é respondido uma vez|
|`test_reply_without_an_evolution_id_is_left_to_the_echo`|`keep`|Sem id na resposta, grava só quando o eco chega|
|`test_failure_to_persist_the_reply_does_not_break_the_turn`|`keep`|Falha ao gravar a reply não quebra Session nem Turn seguinte|
|`test_instance_without_binding_uses_the_agent_of_its_company_and_binds_it`|`keep`|Instance sem Agent usa o da Company e vincula|
|`test_agent_of_another_company_is_never_used`|`keep`|Isolamento: Agent de outra Company jamais é usado|
|`test_missing_agent_logs_one_clear_error_and_never_answers`|`keep`|Sem Agent: um único erro de log e nenhuma resposta|
|`test_disabled_agent_does_not_answer`|`keep`|`agent_enabled=False` grava mas não responde|

#### `tests/whatsapp/test_whatsapp_consumer_lifecycle.py`
10 testes: 10 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_messages_of_one_conversation_run_in_order_and_never_overlap`|`keep`|Lock por Conversation: ordem e sem sobreposição|
|`test_different_conversations_are_processed_in_parallel`|`keep`|Rendezvous prova que Conversations não se serializam|
|`test_conversation_locks_are_released_when_idle`|`keep`|Sem vazamento de Locks por Conversation|
|`test_summary_does_not_delay_the_reply_and_finishes_on_the_persistent_loop`|`keep`|Summary fora do caminho crítico da resposta|
|`test_failing_summary_never_surfaces`|`keep`|Erro do Summary não afeta a resposta|
|`test_stop_waits_for_a_pending_summary`|`keep`|Shutdown espera Summary pendente|
|`test_stop_cancels_a_summary_that_outlives_the_drain_timeout`|`keep`|Shutdown cancela Summary travado após timeout|
|`test_realtime_failure_does_not_stop_the_agent_or_the_reply`|`keep`|Redis fora não derruba Agent nem gravação da reply|
|`test_parse_content_survives_null_message_keys (×5 casos)`|`keep`|Payload com chaves `null` não estoura|
|`test_message_with_null_extended_text_is_stored_and_not_answered`|`keep`|Message malformada é gravada e não respondida|

#### `tests/whatsapp/test_whatsapp_debounce.py`
8 testes: 8 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_three_quick_messages_get_one_turn_and_one_reply`|`keep`|Três Messages viram um Turn e uma resposta, todas gravadas|
|`test_followers_are_stored_while_the_leader_waits`|`keep`|Seguidoras gravadas na hora, sem perda por espera|
|`test_message_arriving_during_a_turn_is_answered_in_the_next_turn_without_overlap`|`keep`|Message durante Turn: próximo Turn, resposta em ordem|
|`test_different_conversations_group_independently_and_run_in_parallel`|`keep`|Agrupamento isolado por Conversation|
|`test_typing_is_shown_while_the_turn_runs_and_stops_after_the_reply`|`keep`|"Digitando" aparece durante o Turn com os parâmetros certos|
|`test_typing_failure_does_not_block_the_reply`|`keep`|Falha da presença não bloqueia a resposta|
|`test_typing_is_not_shown_when_the_agent_will_not_answer`|`keep`|Sem "digitando" quando o Agent não vai responder|
|`test_grouped_turn_is_triggered_at_the_oldest_message_of_the_group`|`keep`|Timestamp do webhook mais antigo dispara o Turn (Recap)|

#### `tests/whatsapp/test_whatsapp_groups.py`
6 testes: 6 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_group_message_is_stored_with_sender_name_and_never_reaches_the_agent`|`keep`|Grupo gravado para a UI, Agent calado, sem Session|
|`test_group_contact_name_is_never_overwritten_by_the_sender_push_name`|`keep`|Nome do grupo não é sobrescrito pelo pushName|
|`test_own_message_in_group_has_no_sender_name`|`keep`|Mensagem própria no grupo sem `sender_name`|
|`test_invisible_message_types_are_not_stored (×8 casos)`|`keep`|Tipos invisíveis (reação, revoke etc.) não são gravados|
|`test_text_with_context_info_is_still_stored`|`keep`|Filtro de invisíveis não derruba texto com contextInfo|
|`test_album_photo_is_stored_as_image`|`keep`|Foto de álbum gravada como imagem com legenda|

#### `tests/whatsapp/test_whatsapp_sessions.py`
6 testes: 6 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_first_message_starts_the_session_at_its_own_timestamp`|`keep`|Session abre no timestamp da primeira Message|
|`test_message_within_the_limit_keeps_the_session_and_the_open_order`|`keep`|Fronteira: 2h59 mantém Session e Order aberto|
|`test_message_after_the_limit_opens_a_new_session_and_abandons_the_open_order`|`keep`|Após o limite: nova Session e Order abandonado|
|`test_limit_comes_from_the_company`|`keep`|Limite vem de `session_timeout_minutes` da Company|
|`test_our_own_reply_after_a_long_pause_does_not_open_a_session`|`keep`|Resposta própria não abre Session|
|`test_pack_without_the_session_hook_still_gets_the_message_saved_and_the_turn_run`|`keep`|Pack sem hook não impede gravar nem rodar Turn|

### Área 3: agent / packs / handoff / llm / scripts

#### `tests/agent/test_agent_events.py`
5 testes: 5 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_thinking_start_e_end_na_sala_da_conversa`|`keep`|Contrato exato do evento thinking que o frontend consome|
|`test_tool_concluida_emite_started_e_completed_com_o_mesmo_trace`|`keep`|Fases started/completed, previews e trace_id único|
|`test_tool_com_erro_emite_failed`|`keep`|Tool com is_error vira fase failed com o erro|
|`test_falha_do_bus_nao_derruba_o_turn`|`keep`|Bus fora não pode quebrar o Turn (try/except real)|
|`test_handoff_publica_um_dict`|`keep`|Mantido (#55): `publish_handoff_requested` só tem este teste de pé; o equivalente em `tests/realtime/test_socket_thinking_events.py` é candidato da Área 2 e aponta para cá.|

#### `tests/agent/test_agent_executor.py`
16 testes: 16 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_conversation_em_handoff_nao_responde_nem_chama_o_modelo`|`keep`|Gate de Handoff relê o estado do banco, não o objeto stale|
|`test_turn_com_tool_usa_a_memoria_e_devolve_resposta_formatada`|`keep`|Turn completo: memória, Tool, ctx e formatação WhatsApp|
|`test_falha_do_gateway_devolve_mensagem_generica_sem_debug`|`keep`|Falha do Gateway não vaza detalhe ao cliente|
|`test_instance_sem_company_nao_responde`|`keep`|Sem Company não chama o modelo nem responde|
|`test_texto_atual_entra_mesmo_com_message_anterior_do_contact_sem_resposta`|`keep`|Mensagem atual não se perde após msg sem resposta|
|`test_falha_no_turn_desfaz_a_session_para_quem_chama`|`keep`|Rollback preserva a Session do consumer após erro|
|`test_attendant_que_assume_durante_o_turn_cala_o_agent`|`keep`|Race: Attendant assume no meio do Turn, Agent calado|
|`test_tool_que_transfere_ainda_envia_a_mensagem_de_transferencia`|`keep`|Handoff via Tool ainda envia a frase de transferência|
|`test_refresh_summary_usa_session_propria_e_falha_nao_afeta_a_resposta`|`keep`|Resumo em Session própria; falha não afeta resposta|
|`test_prompt_traz_data_e_hora_no_fuso_da_company`|`keep`|Prompt traz data/hora local no fuso da Company|
|`test_prompt_muda_de_dia_conforme_o_fuso_da_company`|`keep`|Fuso muda o dia local (virada de data)|
|`test_prompt_diz_ha_quanto_tempo_foi_a_mensagem_anterior`|`keep`|Tempo desde a Message anterior no prompt|
|`test_prompt_marca_a_volta_depois_de_pausa_longa_e_a_janela_so_tem_a_session_atual`|`keep`|Novo atendimento após pausa e janela só da Session|
|`test_prompt_da_primeira_mensagem_nao_inventa_mensagem_anterior`|`keep`|Primeira mensagem não inventa mensagem anterior|
|`test_turn_usa_temperatura_e_limite_de_tokens_do_agent_da_company`|`keep`|Config do Agent da Company chega ao request|
|`test_company_sem_agent_cadastrado_usa_os_padroes`|`keep`|Sem Agent cadastrado cai no fallback de tokens|

#### `tests/agent/test_agent_formatting.py`
9 testes: 9 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_valor_monetario_fica_intacto`|`keep`|Valores R$ 1.250,00 não podem ser corrompidos|
|`test_valor_monetario_dentro_de_negrito`|`keep`|Interação negrito + valor monetário|
|`test_negrito_markdown_vira_negrito_whatsapp`|`keep`|`**x**` vira `*x*`|
|`test_italico_e_tachado`|`keep`|`__x__` e `~~x~~` viram sintaxe WhatsApp|
|`test_titulo_vira_negrito`|`keep`|Título markdown vira negrito|
|`test_lista_markdown_vira_bullet`|`keep`|Marcadores `-`/`*` viram bullet|
|`test_lista_numerada_preservada`|`keep`|Lista numerada não é alterada|
|`test_link_markdown_vira_texto_e_url`|`keep`|Link markdown vira texto + URL|
|`test_espacos_e_linhas_em_branco_excedentes`|`keep`|Limpa espaços e linhas em branco extras|

#### `tests/agent/test_agent_loop.py`
11 testes: 11 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_turn_sem_tools_devolve_o_texto_do_modelo`|`keep`|Turn sem Tool devolve texto e monta request|
|`test_um_tool_use_e_executado_e_o_resultado_volta_ao_modelo`|`keep`|Tool executada e tool_result volta ao modelo|
|`test_varios_tool_use_executam_em_ordem_e_voltam_juntos`|`keep`|Ordem de execução e agrupamento dos resultados|
|`test_tool_com_erro_volta_como_is_error_e_o_turn_continua`|`keep`|Exceção vira is_error genérico e o Turn segue|
|`test_ends_turn_para_sem_chamar_o_modelo_de_novo_e_responde_a_mensagem_da_tool`|`keep`|ends_turn interrompe Tools seguintes e novo request|
|`test_max_steps_faz_chamada_final_com_schemas_e_ignora_tool_use_dela`|`keep`|Limite de passos: chamada final sem novas Tools|
|`test_max_tokens_e_temperature_chegam_a_toda_chamada_inclusive_a_final`|`keep`|Parâmetros chegam inclusive à chamada final|
|`test_max_steps_sem_texto_na_chamada_final_responde_mensagem_fixa`|`keep`|Fallback quando a chamada final não traz texto|
|`test_resposta_sem_texto_significa_nao_responder`|`keep`|Texto em branco = não responder|
|`test_historico_do_chamador_nao_e_alterado`|`keep`|Loop não muta o histórico do chamador|
|`test_flush_que_falha_numa_tool_nao_quebra_a_proxima_tool_do_turn`|`keep`|Rollback isola falha de flush entre Tools|

#### `tests/agent/test_agent_tools.py`
7 testes: 7 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_schemas_no_formato_messages_de_todos_os_packs`|`keep`|Schemas de todos os Packs no formato da API|
|`test_nome_de_tool_duplicado_entre_packs_e_recusado`|`keep`|Colisão de nomes entre Packs é recusada|
|`test_execute_devolve_tool_result_do_handler`|`keep`|tool_result com id correto e ends_turn falso|
|`test_input_invalido_vira_erro_sem_chamar_o_handler`|`keep`|Validação de schema barra o handler|
|`test_excecao_do_handler_vira_erro_generico_sem_vazar_detalhe`|`keep`|Exceção não vaza detalhe interno|
|`test_tool_desconhecida_vira_erro`|`keep`|Tool inexistente vira erro, não exceção|
|`test_ends_turn_e_erro_do_handler_sao_repassados`|`keep`|Único teste de is_error devolvido pelo handler via registry|

#### `tests/agent/test_business_hours.py`
13 testes: 13 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_open_within_simple_interval`|`keep`|Bordas inclusiva/exclusiva do intervalo|
|`test_interval_crossing_midnight_stays_open_after_midnight`|`keep`|Turno que cruza a meia-noite segue aberto|
|`test_end_midnight_means_until_end_of_day`|`keep`|Regressão: fim 00:00 = até o fim do dia|
|`test_midnight_crossing_from_sunday_wraps_to_monday`|`keep`|Virada domingo para segunda|
|`test_missing_day_is_closed_and_no_hours_is_unknown`|`keep`|Dia ausente fechado; sem horários = None|
|`test_multiple_intervals_per_day`|`keep`|Vários intervalos no mesmo dia|
|`test_next_opening_later_today`|`keep`|Próxima abertura ainda hoje|
|`test_next_opening_tomorrow_after_closing`|`keep`|Próxima abertura no dia seguinte|
|`test_next_opening_skips_closed_days`|`keep`|Pula dias fechados|
|`test_next_opening_wraps_to_next_week_same_weekday`|`keep`|Volta à semana seguinte no mesmo dia|
|`test_next_opening_picks_earliest_interval_of_the_day`|`keep`|Escolhe o menor intervalo mesmo fora de ordem|
|`test_next_opening_is_none_without_hours_or_intervals`|`keep`|Sem horários/intervalos devolve None|
|`test_describe_opening_uses_today_tomorrow_and_weekday_names`|`keep`|Quatro ramos da frase de abertura mostrada ao cliente|

#### `tests/agent/test_clock.py`
1 teste: 1 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_invalid_company_timezone_falls_back_to_the_default_zone` (×5 casos)|`keep`|Fuso inválido/malicioso não derruba o Turn|

#### `tests/agent/test_conversation_memory.py`
18 testes: 18 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_build_context_returns_only_the_last_window_in_order`|`keep`|Janela de 20 mensagens em ordem|
|`test_build_context_merges_consecutive_messages_of_the_same_role`|`keep`|Funde mensagens consecutivas do mesmo papel|
|`test_build_context_starts_with_a_user_message`|`keep`|Histórico sempre começa com user|
|`test_build_context_ignores_media_and_empty_messages`|`keep`|Ignora mídia e mensagens vazias|
|`test_summary_is_not_generated_below_twenty_messages_outside_the_window`|`keep`|Limite: 19 fora da janela não resume|
|`test_summary_is_generated_with_twenty_messages_outside_the_window`|`keep`|Limite: 20 fora da janela dispara resumo|
|`test_summary_is_not_regenerated_until_twenty_new_messages_leave_the_window`|`keep`|Resumo incremental só após 20 novas|
|`test_summary_is_capped_at_1200_characters`|`keep`|Resumo truncado em 1200 caracteres|
|`test_summary_failure_is_only_logged`|`keep`|Falha do Gateway no resumo não propaga|
|`test_search_history_finds_old_messages_across_the_contact_conversations`|`keep`|Busca alcança todas as Conversations do Contact|
|`test_search_history_never_returns_other_contacts_or_instances`|`keep`|Isolamento entre Contacts e Instances|
|`test_search_history_requires_every_term_and_is_case_insensitive`|`keep`|AND de termos, sem diferenciar caixa|
|`test_search_history_treats_like_wildcards_literally`|`keep`|`%` na consulta não vira curinga|
|`test_search_history_limits_results_and_truncates_snippets`|`keep`|Limite de resultados, snippet e ordem recente primeiro|
|`test_search_history_with_blank_query_returns_nothing`|`keep`|Consulta em branco não varre o histórico|
|`test_search_history_snippet_is_centered_on_the_first_match`|`keep`|Snippet em volta do termo, não só o início|
|`test_summary_batch_is_capped_at_the_100_oldest_pending_messages`|`keep`|Lote de 100 e continuação no próximo resumo|
|`test_summary_refresh_follows_the_window_it_is_given`|`keep`|Resumo respeita a janela informada|

#### `tests/agent/test_core_tools.py`
14 testes: 14 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_info_empresa_open_now_uses_company_timezone`|`keep`|aberto_agora usa fuso local na virada de dia|
|`test_info_empresa_timezone_changes_the_answer`|`keep`|Lê timezone da Company, não fuso fixo|
|`test_info_empresa_fields`|`keep`|Endereço, horários, pagamento e taxas formatados|
|`test_info_empresa_is_scoped_to_context_company`|`keep`|Não vaza dados de outra Company|
|`test_info_empresa_without_hours_or_pix`|`keep`|Sem horário/pix: None e sem forma pix|
|`test_transfer_creates_ticket_with_contact_fk_and_flags_conversation`|`keep`|Ticket com FK correta e Conversation em Handoff|
|`test_transfer_falls_back_to_reason_when_no_incoming_message`|`keep`|Conteúdo do Ticket cai no motivo|
|`test_transfer_is_idempotent_per_conversation`|`keep`|Um só Ticket e um só evento por Conversation|
|`test_transfer_requires_reason`|`keep`|Motivo em branco é erro sem Ticket|
|`test_transfer_survives_event_bus_failure`|`keep`|Bus fora não impede a transferência|
|`test_buscar_historico_with_no_match_returns_empty_list`|`keep`|Sem resultado devolve lista vazia, não erro|
|`test_buscar_historico_blank_query_is_error`|`keep`|Consulta em branco é erro da Tool|
|`test_six_tools_in_total`|`keep`|Mantido (#55): nenhum outro teste monta um `ToolRegistry` com as Tools reais do núcleo e do Pack; `from_packs` só recusa duplicata nos testes com Packs falsos.|
|`test_buscar_historico_uses_memory_search_scoped_to_contact`|`keep`|Tool filtra pelo Contact do ctx|

#### `tests/agent/test_handoff_socket.py`
3 testes: 3 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_handoff_event_from_the_tool_reaches_instance_and_conversation_rooms`|`keep`|Evento montado pela Tool chega às duas salas|
|`test_handoff_event_without_conversation_is_not_emitted`|`keep`|Sem conversation_id não emite para sala inválida|
|`test_handoff_event_without_instance_is_dropped_like_other_events`|`keep`|Mantido (#55): o equivalente em `tests/realtime/test_socket_thinking_events.py` é candidato da Área 2 e aponta para cá; sobra só este para o descarte sem `instance_name`.|

#### `tests/agent/test_sessions.py`
15 testes: 15 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_first_message_of_a_conversation_opens_its_session`|`keep`|Primeira mensagem registra início da Session|
|`test_message_exactly_at_the_limit_continues_and_one_second_later_opens_a_new_session`|`keep`|Fronteira exata do timeout de Session|
|`test_limit_is_configurable_per_company`|`keep`|Timeout lido da Company|
|`test_naive_datetimes_from_the_database_are_compared_as_utc`|`keep`|Datetime naive do banco tratado como UTC|
|`test_expired_session_notifies_every_pack_and_a_continued_one_does_not`|`keep`|Hook de Session só quando expira|
|`test_pack_without_the_session_hook_does_not_break_a_new_session`|`keep`|Pack sem hook não quebra a Session nova|
|`test_a_late_backlog_message_does_not_open_a_session`|`keep`|Mensagem atrasada de backlog não abre Session|
|`test_recent_window_has_only_messages_of_the_current_session`|`keep`|Janela só com mensagens da Session atual|
|`test_conversation_without_a_recorded_session_keeps_the_whole_window`|`keep`|Conversation legada mantém janela inteira|
|`test_history_search_and_summary_still_reach_previous_sessions`|`keep`|Resumo e busca alcançam Sessions anteriores|
|`test_messages_of_a_previous_session_count_as_outside_the_window_for_the_summary`|`keep`|Sessions antigas contam como fora da janela no resumo|
|`test_previous_message_skips_every_message_grouped_into_the_turn`|`keep`|Mensagem anterior ignora o grupo do Turn|
|`test_previous_message_keeps_an_earlier_unanswered_message_of_the_contact`|`keep`|Mensagem anterior sem resposta continua válida|
|`test_previous_message_skips_a_reply_that_sits_between_grouped_messages`|`keep`|Resposta fixa no meio do grupo ainda é a anterior|
|`test_previous_message_is_none_when_the_whole_conversation_is_the_turn`|`keep`|Sem mensagem anterior devolve None|

#### `tests/handoff/test_handoff_api.py`
12 testes: 12 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_take_control_opens_ticket_assigned_to_the_attendant`|`keep`|Assumir abre Ticket atribuído e emite evento|
|`test_take_control_on_agent_requested_handoff_assigns_the_same_ticket`|`keep`|Assumir reaproveita o Ticket do Agent|
|`test_release_control_closes_ticket_and_returns_to_agent`|`keep`|Devolver fecha Ticket e libera Conversation|
|`test_release_without_handoff_changes_nothing`|`keep`|Devolver sem Handoff é no-op sem evento|
|`test_state_survives_reload_through_the_listing`|`keep`|Estado persiste na listagem de Conversations|
|`test_other_users_cannot_take_or_release`|`keep`|Autorização: outra Company recebe 403|
|`test_second_attendant_cannot_take_a_conversation_already_held`|`keep`|Segundo Attendant recebe 409 sem evento|
|`test_same_attendant_taking_again_is_idempotent`|`keep`|Assumir de novo é idempotente|
|`test_another_attendant_can_take_after_the_conversation_was_released`|`keep`|Após devolver, outro Attendant pode assumir|
|`test_release_after_timeout_already_returned_it_changes_and_announces_nothing`|`keep`|Devolver após expiração não altera nem anuncia|
|`test_status_endpoint_is_read_only_even_when_the_timeout_is_due`|`keep`|GET de status não muda estado mesmo vencido|
|`test_status_endpoint_reports_not_due_inside_the_timeout`|`keep`|timeout_due falso dentro do prazo|

#### `tests/handoff/test_handoff_reply.py`
11 testes: 11 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_open_hours_reply_is_the_empathy_then_the_fixed_phrase`|`keep`|Aberto: empatia + frase fixa|
|`test_after_hours_reply_says_when_the_next_window_opens_today`|`keep`|Fechado: informa abertura hoje|
|`test_after_hours_reply_points_to_tomorrow`|`keep`|Fechado após o expediente aponta amanhã|
|`test_friday_midnight_close_points_to_saturday_window`|`keep`|Fechamento 00:00 de sexta aponta sábado|
|`test_company_without_hours_always_uses_the_fixed_phrase`|`keep`|Sem horários usa a frase fixa|
|`test_blank_empathy_falls_back_to_the_fixed_phrase_alone`|`keep`|Empatia em branco cai só na frase fixa|
|`test_multiline_empathy_is_collapsed_to_one_line`|`keep`|Empatia multilinha vira uma linha|
|`test_transfer_without_empathy_goes_through_the_registry_and_still_hands_off`|`keep`|Registry não barra transferência sem frase empática|
|`test_registry_still_rejects_a_transfer_without_reason`|`keep`|Registry rejeita transferência sem motivo|
|`test_overnight_window_is_open_after_midnight_and_closed_before_it_opens`|`keep`|Janela noturna na frase de Handoff|
|`test_company_with_hours_but_no_open_day_says_to_wait_without_a_time`|`keep`|Horários sem dia aberto: espera sem horário|

#### `tests/handoff/test_handoff_timeout.py`
10 testes: 10 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_handoff_without_attendant_expires_after_the_company_timeout`|`keep`|Vencido expira Ticket e devolve ao Agent|
|`test_handoff_inside_the_timeout_is_left_alone`|`keep`|Dentro do prazo nada muda|
|`test_timeout_is_configured_per_company`|`keep`|Prazo vem da Company|
|`test_attendant_activity_restarts_the_timeout`|`keep`|Atividade recente do Attendant adia expiração|
|`test_recording_attendant_activity_postpones_expiry`|`keep`|record_attendant_activity reinicia o prazo|
|`test_conversation_without_handoff_is_never_expired`|`keep`|Sweeper ignora Conversation sem Handoff|
|`test_released_ticket_cannot_become_expired_afterwards`|`keep`|Ticket fechado não vira expirado|
|`test_release_racing_the_sweeper_makes_a_single_transition`|`keep`|Race: devolução vence o sweeper, um só anúncio|
|`test_expire_racing_a_release_makes_a_single_transition`|`keep`|Race inversa: expirar vence, devolução vira no-op|
|`test_new_handoff_after_the_judged_one_ended_is_not_expired`|`keep`|Ticket novo não é expirado por julgamento stale|

#### `tests/llm/test_gateway_inference.py`
21 testes: 21 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_posts_to_v1_messages_with_anthropic_headers`|`keep`|URL `/v1/messages` normalizada e headers de auth/versão|
|`test_request_body_maps_contract_fields_and_effort`|`keep`|Payload exato enviado ao provedor, incluindo tool_use/tool_result e `output_config`|
|`test_optional_fields_are_omitted_when_unset`|`keep`|Campos opcionais e `x-api-key` ausentes quando não configurados|
|`test_text_response_is_mapped`|`keep`|Resposta Messages vira contrato do agente|
|`test_tool_use_response_is_mapped_and_thinking_is_dropped`|`keep`|Bloco `thinking` descartado, `tool_use` preservado|
|`test_retries_rate_limit_then_succeeds`|`keep`|Retry de 429/503 até sucesso (3 requests)|
|`test_rate_limit_gives_up_after_three_attempts`|`keep`|Limite de 3 tentativas e tipo `LLMRateLimitError`|
|`test_server_error_gives_up_after_three_attempts_with_status`|`keep`|5xx esgota retries e expõe `status_code`|
|`test_timeout_is_retried_and_typed`|`keep`|Timeout vira `LLMTimeoutError` após 3 tentativas|
|`test_client_error_is_not_retried`|`keep`|4xx não repete (1 request)|
|`test_error_message_never_contains_api_key`|`keep`|Vazamento da chave de API na mensagem de erro|
|`test_malformed_json_response_is_a_provider_error_and_not_retried (×14 casos)`|`keep`|JSON 200 malformado sempre `LLMProviderError`, sem retry|
|`test_non_json_body_is_a_provider_error (×3 casos)`|`keep`|Corpo vazio/HTML/truncado vira `LLMProviderError`|
|`test_missing_usage_and_stop_reason_use_safe_defaults`|`keep`|Defaults tolerantes quando faltam `usage`/`stop_reason`|
|`test_list_models_malformed_body_is_a_provider_error (×5 casos)`|`keep`|`list_models` com `data` ausente/inválido → erro tipado|
|`test_max_attempts_one_disables_retry`|`keep`|`max_attempts=1` realmente desliga o retry|
|`test_probe_uses_messages_with_max_tokens_8`|`keep`|Probe barato: `max_tokens` 8, effort e texto/latência|
|`test_list_models_reads_v1_models`|`keep`|GET `/v1/models` e extração dos ids|
|`test_list_models_404_carries_status_code`|`keep`|404 expõe `status_code` ao consumidor|
|`test_secret_roundtrip_and_ciphertext_hides_plaintext`|`keep`|Roundtrip e texto cifrado sem o segredo em claro|
|`test_secret_key_is_derived_with_hkdf_not_plain_sha256`|`keep`|Mantido (#55): único teste que prova que `decrypt_secret` recusa token SHA-256 legado; `test_llm_registry.py::test_reencrypt_*` só prova a migração.|

#### `tests/llm/test_llm_registry.py`
10 testes: 10 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_resolve_returns_client_model_and_effort`|`keep`|`resolve` devolve cliente, model_id e effort da atribuição|
|`test_resolve_prefers_specific_assignment_then_default`|`keep`|Precedência atribuição específica > default|
|`test_resolve_without_any_assignment_raises_not_configured`|`keep`|Sem atribuição levanta `LLMNotConfiguredError`|
|`test_resolve_inactive_model_raises_not_configured`|`keep`|Modelo inativo não é resolvido|
|`test_inactive_specific_assignment_does_not_fall_back_to_default`|`keep`|Atribuição específica inativa não cai no default|
|`test_undecryptable_api_key_raises_explicitly_and_is_not_cached`|`keep`|Chave ilegível falha explícito e não é cacheada|
|`test_resolution_is_cached_until_invalidated`|`keep`|Cache de resolução e `invalidate()`|
|`test_ensure_default_gateway_seeds_kiro_backend_with_messages_model_and_is_idempotent`|`keep`|Seed idempotente que preserva edição do usuário|
|`test_reencrypt_migrates_legacy_sha256_tokens_and_is_idempotent`|`keep`|Migração de tokens legados sem tocar nos atuais/sem chave|
|`test_reencrypt_skips_tokens_that_open_with_neither_key`|`keep`|Token irrecuperável é ignorado sem quebrar|

#### `tests/packs/test_pack_catalog_search.py`
13 testes: 13 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_multi_word_query_finds_item`|`keep`|Busca multi-palavra devolve id, preço e descrição corretos|
|`test_scope_is_the_context_company_not_a_hardcoded_name`|`keep`|Isolamento por Company: item da outra não vaza|
|`test_accent_and_case_insensitive`|`keep`|Busca ignora acento e caixa|
|`test_whole_word_match_pizza_does_not_hit_pizzaiolo`|`keep`|Casa palavra inteira, não substring|
|`test_simple_plural`|`keep`|Plural simples encontra o item|
|`test_all_tokens_must_match`|`keep`|Todos os termos precisam casar (AND)|
|`test_query_matches_category_name`|`keep`|Consulta casa pelo nome da categoria|
|`test_categoria_filter`|`keep`|Filtro de categoria combina com a consulta|
|`test_unavailable_items_are_never_returned`|`keep`|Item indisponível nunca é oferecido|
|`test_result_is_capped_at_15`|`keep`|Limite de 15 itens e total_encontrado correto|
|`test_description_is_shortened`|`keep`|Descrição longa é truncada em 120|
|`test_inactive_catalog_is_ignored`|`keep`|Cardápio inativo não aparece na busca|
|`test_empty_search_lists_categories_and_first_items`|`keep`|Busca vazia lista categorias na ordem e primeiros itens|

#### `tests/packs/test_pack_changes.py`
25 testes: 25 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_cancel_right_after_confirming_cancels_without_handoff`|`keep`|Cancelar pedido recém-confirmado, sem Ticket nem handoff|
|`test_cancel_after_preparation_started_is_refused_and_points_to_handoff (×3 casos)`|`keep`|Cancelar em preparo/enviado/entregue é recusado e aponta handoff|
|`test_cancel_of_an_already_cancelled_order_is_refused`|`keep`|Não cancela duas vezes|
|`test_cancel_without_any_order_is_refused`|`keep`|Cancelar sem nenhum pedido dá erro|
|`test_cancel_never_touches_the_order_of_another_conversation`|`keep`|Cancelar não alcança Order de outra Conversation|
|`test_cancel_with_pix_invalidates_the_record_and_flags_the_refund`|`keep`|Cancelar com Pix invalida registro e marca "verify"|
|`test_cancel_of_a_paid_pix_flags_it_to_be_refunded`|`keep`|Pix pago cancelado fica pendente de estorno|
|`test_cancel_without_pix_leaves_no_refund_flag`|`keep`|Cancelar pagamento em dinheiro não cria registro Pix|
|`test_cancel_after_preparation_with_pix_does_not_touch_the_payment_record`|`keep`|Cancelamento recusado preserva o Pix pendente|
|`test_alter_reopens_the_order_and_requires_a_new_confirmed_recap`|`keep`|Alterar reabre e invalida a confirmação antiga|
|`test_alter_adding_an_item_recomputes_the_total_and_asks_for_confirmation`|`keep`|Alteração recalcula total e refecha após nova recap|
|`test_alter_changing_the_address_recomputes_the_delivery_fee`|`keep`|Trocar para retirada zera a taxa e o total|
|`test_alter_after_preparation_started_is_refused_and_points_to_handoff (×3 casos)`|`keep`|Alterar em preparo é recusado e preserva a Recap|
|`test_alter_of_a_cancelled_or_abandoned_order_is_refused (×2 casos)`|`keep`|Não altera pedido cancelado ou abandonado|
|`test_alter_is_refused_while_another_order_is_being_built`|`keep`|Recusa alterar com outro pedido em montagem|
|`test_alter_on_an_order_still_being_built_is_refused`|`keep`|Alterar pedido ainda não confirmado dá erro|
|`test_cancel_while_the_alteration_is_pending_cancels_the_order`|`keep`|Cancelar durante alteração pendente funciona|
|`test_alter_with_pix_supersedes_the_old_record_and_issues_a_new_one_with_the_new_amount`|`keep`|Pix antigo superado e novo emitido com o novo valor|
|`test_repeated_alterations_never_leave_two_valid_pix_records`|`keep`|Invariante: no máximo um Pix válido por Order|
|`test_alter_that_moves_payment_from_pix_to_cash_leaves_no_valid_pix`|`keep`|Trocar Pix por dinheiro deixa zero Pix válido|
|`test_regenerated_pix_has_a_distinct_valid_txid`|`keep`|Cada Pix regenerado tem txid distinto e válido|
|`test_cancel_refuses_to_pick_between_a_building_order_and_a_closed_one`|`keep`|Ambiguidade de cancelamento exige escolha do Contact|
|`test_cancel_with_the_order_number_cancels_exactly_that_order`|`keep`|Cancelar por número atinge só o Order indicado|
|`test_cancel_of_a_building_order_is_refused`|`keep`|Pedido em montagem não se cancela; usa remover_item|
|`test_cancel_of_an_abandoned_order_is_refused_and_points_to_resume`|`keep`|Pedido abandonado não cancela; aponta retomar_pedido|

#### `tests/packs/test_pack_changes_sessions.py`
10 testes: 10 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_order_from_days_ago_is_not_changed_here_and_leads_to_handoff`|`keep`|Order de sessão antiga não é alterado; leva a handoff|
|`test_order_confirmed_in_the_previous_session_can_still_be_cancelled`|`keep`|Fronteira: Order da sessão anterior ainda cancela|
|`test_session_rollover_during_an_alteration_restores_the_confirmed_order`|`keep`|Virada de Session restaura o pedido confirmado e o Pix|
|`test_restored_order_can_be_altered_again_and_gets_a_new_distinct_pix`|`keep`|Pedido restaurado é alterável e gera novo Pix distinto|
|`test_session_rollover_still_abandons_a_plain_open_order_but_not_the_reopened_one`|`keep`|Virada abandona só o pedido simples, não o reaberto|
|`test_reopened_order_without_snapshot_is_never_abandoned`|`keep`|Reaberto sem snapshot nunca vira abandonado|
|`test_view_marks_the_reopened_order_as_being_altered`|`keep`|`ver` sinaliza em_alteracao só após reabrir|
|`test_resume_after_an_alteration_is_refused_while_the_order_is_being_altered`|`keep`|Não retoma enquanto há pedido em alteração|
|`test_resume_after_cancelling_an_altered_order_has_nothing_to_resume`|`keep`|Cancelado após alteração não deixa nada a retomar|
|`test_resume_works_for_a_plain_abandoned_order_even_with_a_restored_one_before`|`keep`|Retomada ignora o restaurado e pega o abandonado|

#### `tests/packs/test_pack_checkout.py`
19 testes: 19 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_invalid_names_are_refused (×7 casos)`|`keep`|Recusa nomes que são palavras de fluxo ou curtos demais|
|`test_valid_name_is_stored`|`keep`|Nome curto válido ("Zé") é gravado|
|`test_invalid_delivery_addresses_are_refused (×4 casos)`|`keep`|Endereço sem número ou sem bairro é recusado|
|`test_address_not_required_for_pickup`|`keep`|Retirada dispensa endereço; falta só pagamento|
|`test_invalid_enums_are_refused`|`keep`|Pagamento e entrega fora do enum são recusados|
|`test_invalid_field_saves_nothing`|`keep`|Campo inválido não grava os válidos junto|
|`test_definir_dados_without_order_is_error`|`keep`|definir_dados sem pedido retorna erro|
|`test_pix_payment_is_refused_early_when_company_has_no_key`|`keep`|Pix recusado cedo se a Company não tem chave|
|`test_total_includes_zone_fee_for_delivery`|`keep`|Total soma taxa da zona e é persistido|
|`test_pickup_has_no_fee`|`keep`|Retirada não cobra taxa|
|`test_zone_of_other_company_or_legacy_is_not_used`|`keep`|Zona de outra Company ou legada não vale|
|`test_delivery_without_configured_zone_is_unavailable`|`keep`|Sem zona, entrega indisponível e sugere retirada|
|`test_minimum_order_blocks_finalize_and_counts_items_only`|`keep`|Pedido abaixo do mínimo não fecha; erro cita 30|
|`test_finalize_requires_complete_data`|`keep`|Finalizar lista os campos faltantes|
|`test_finalize_delivery_requires_address`|`keep`|Entrega sem endereço não finaliza|
|`test_finalize_without_items_is_error`|`keep`|Pedido vazio não finaliza|
|`test_finalize_cash_closes_order_with_total`|`keep`|Fechamento em dinheiro: total, troco, telefone, sem Pix|
|`test_change_must_cover_total`|`keep`|Troco menor que o total ou fora de dinheiro é recusado|
|`test_after_finalize_a_new_order_starts_empty`|`keep`|Após fechar, novo item abre Order novo|

#### `tests/packs/test_pack_closing.py`
20 testes: 20 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_finalize_without_recap_is_refused`|`keep`|Sem recapitular, finalizar é recusado|
|`test_finalize_in_the_same_turn_as_the_recap_is_refused`|`keep`|Recap e finalizar no mesmo Turn não fecham|
|`test_recap_whose_reply_never_reached_the_contact_does_not_allow_finalize`|`keep`|Recap não entregue não libera finalizar|
|`test_delivery_of_another_turns_reply_does_not_validate_the_recap`|`keep`|Entrega de outro Turn não valida a Recap|
|`test_confirmation_typed_before_the_recap_was_delivered_does_not_close`|`keep`|Fronteira de trigger_at <= entrega não fecha|
|`test_recap_returns_the_order_with_the_real_total`|`keep`|Recap mostra o total real com taxa|
|`test_recap_of_an_incomplete_order_is_refused_and_does_not_unlock_finalize`|`keep`|Recap incompleta é recusada e não libera fechamento|
|`test_any_change_after_the_recap_requires_a_new_recap (×8 casos)`|`keep`|Qualquer mudança pós-Recap invalida a confirmação|
|`test_repeating_the_recap_with_nothing_changed_keeps_the_confirmation_valid`|`keep`|Recap repetida sem mudança mantém confirmação válida|
|`test_cash_change_edit_after_the_recap_requires_a_new_recap`|`keep`|Mudar troco_para pós-Recap exige nova Recap|
|`test_a_resumed_order_needs_its_own_recap`|`keep`|Pedido retomado não herda a Recap antiga|
|`test_adding_the_same_item_twice_in_one_turn_does_not_duplicate`|`keep`|Repetição idêntica no mesmo Turn é ignorada|
|`test_adding_the_same_item_with_another_quantity_in_one_turn_is_added`|`keep`|Mesma linha com quantidade diferente soma|
|`test_same_item_with_another_note_in_the_same_turn_is_a_separate_line`|`keep`|Observação diferente vira linha separada|
|`test_item_removed_and_added_again_in_the_same_turn_is_added`|`keep`|Remover e re-adicionar no mesmo Turn adiciona de fato|
|`test_finalize_is_refused_when_the_company_is_closed_and_says_when_it_opens`|`keep`|Empresa fechada recusa e informa quando abre|
|`test_closed_after_the_last_window_points_to_tomorrow`|`keep`|Após a última janela, aponta amanhã|
|`test_window_crossing_midnight_is_open_after_midnight_and_closed_at_dawn`|`keep`|Janela que cruza meia-noite está aberta às 01:00|
|`test_window_crossing_midnight_refuses_at_dawn_and_says_when_it_opens`|`keep`|Janela cruzando meia-noite fecha às 03:00|
|`test_company_without_business_hours_can_always_close`|`keep`|Sem horário configurado, sempre pode fechar|

#### `tests/packs/test_pack_items.py`
17 testes: 17 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_add_item_uses_catalog_price_and_quantity`|`keep`|Preço vem do catálogo; subtotal e Order corretos|
|`test_same_item_and_note_accumulates_quantity`|`keep`|Mesmo item e nota em Turn novo acumula quantidade|
|`test_unavailable_item_is_refused`|`keep`|Item indisponível é recusado sem criar Order|
|`test_item_from_other_company_is_refused`|`keep`|Item de outra Company é recusado|
|`test_item_from_inactive_catalog_is_refused_like_the_search`|`keep`|Cardápio inativo recusa adição como a busca|
|`test_unknown_item_and_bad_quantity_are_refused`|`keep`|Item inexistente, sem id e quantidade ≤ 0 recusados|
|`test_remove_item_partial_and_total`|`keep`|Remoção parcial e total recalculam subtotal|
|`test_remove_quantity_spans_multiple_lines_of_the_same_item`|`keep`|Remoção desconta das linhas mais recentes primeiro|
|`test_remove_quantity_inside_the_last_line_keeps_the_others`|`keep`|Remoção dentro da última linha preserva as demais|
|`test_remove_more_than_ordered_clears_every_line_of_the_item`|`keep`|Remover mais que o pedido zera as linhas do item|
|`test_remove_without_quantity_clears_every_line_of_the_item`|`keep`|Sem quantidade remove todas as linhas e zera subtotal|
|`test_remove_item_not_in_order_is_error`|`keep`|Remover item fora do pedido dá erro|
|`test_ver_without_order_says_empty`|`keep`|`ver` sem pedido devolve pedido None sem erro|
|`test_unknown_action_is_error`|`keep`|Ação desconhecida retorna erro|
|`test_status_without_orders`|`keep`|status_pedido sem pedidos devolve None|
|`test_status_returns_latest_order_of_the_contact`|`keep`|status_pedido devolve o Order mais recente|
|`test_status_never_shows_orders_of_another_contact`|`keep`|Status não vaza pedido de outro Contact|

#### `tests/packs/test_pack_pix.py`
11 testes: 11 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_crc16_matches_the_ccitt_false_check_vector`|`keep`|CRC16 contra vetor padrão CCITT-FALSE|
|`test_build_emv_matches_the_known_fixture`|`keep`|BR Code idêntico a fixture com CRC independente|
|`test_merchant_name_and_city_are_ascii_uppercase_and_truncated`|`keep`|Nome/cidade em ASCII maiúsculo e truncados no limite|
|`test_emv_field_over_99_chars_raises_pix_error`|`keep`|Campo EMV acima de 99 caracteres levanta PixError|
|`test_pix_uses_real_amount_company_key_and_order_txid`|`keep`|Pix usa valor real, chave da Company e txid do Order|
|`test_pix_without_company_key_does_not_close_order`|`keep`|Chave removida antes de fechar não fecha nem cria registro|
|`test_pix_key_too_long_returns_clear_error_and_keeps_order_open`|`keep`|Chave longa dá erro claro e mantém Order aberto|
|`test_pix_payment_record_is_deduplicated`|`keep`|ensure_payment_record é idempotente: um registro só|
|`test_unique_index_rejects_a_second_pix_for_the_same_order`|`keep`|Índice único impede segundo Pix por Order|
|`test_unique_index_only_covers_pix`|`keep`|Índice parcial não bloqueia outro método de pagamento|
|`test_ensure_payment_record_recovers_when_a_concurrent_insert_wins`|`keep`|Corrida de insert concorrente retorna o registro vencedor|

#### `tests/packs/test_pack_sessions.py`
15 testes: 15 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_new_session_abandons_the_open_order_and_keeps_its_items`|`keep`|Session nova abandona o Order aberto preservando itens|
|`test_every_active_status_is_abandoned (×3 casos)`|`keep`|Todo status ativo vira abandoned|
|`test_orders_already_finished_are_never_touched (×5 casos)`|`keep`|Status finalizados nunca são tocados|
|`test_other_conversations_keep_their_open_orders`|`keep`|Abandono não atravessa Conversations|
|`test_an_abandoned_order_is_never_resumed_by_adding_an_item`|`keep`|Adicionar item cria Order novo, não reabre abandonado|
|`test_prompt_tells_the_agent_about_the_abandoned_order`|`keep`|Prompt informa número, itens, total e retomar_pedido|
|`test_prompt_has_no_abandoned_note_without_an_abandoned_order`|`keep`|Sem abandonado, o prompt não traz a nota|
|`test_prompt_drops_the_note_once_a_newer_order_exists`|`keep`|Nota some quando há pedido mais novo|
|`test_empty_abandoned_order_is_not_offered`|`keep`|Abandonado vazio não é oferecido|
|`test_resume_recreates_the_order_from_the_abandoned_one`|`keep`|Retomar recria Order novo com os itens e total|
|`test_resume_uses_current_catalog_prices_and_reports_unavailable_items`|`keep`|Retomar usa preço atual e reporta indisponíveis|
|`test_resume_with_nothing_available_fails_and_creates_no_order`|`keep`|Sem itens disponíveis falha sem criar Order|
|`test_resume_without_an_abandoned_order_fails`|`keep`|Retomar sem abandonado dá erro|
|`test_resume_is_refused_while_another_order_is_being_built`|`keep`|Não retoma com outro pedido em montagem|
|`test_same_as_yesterday_from_a_closed_order_via_status_then_add_item`|`keep`|"O mesmo de ontem" recria itens com preços atuais|

#### `tests/packs/test_pack_status_panel.py`
4 testes: 4 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_after_the_company_starts_preparing_the_contact_can_no_longer_cancel_or_alter_and_is_offered_handoff`|`keep`|Em preparo bloqueia cancelar/alterar sem efeitos colaterais|
|`test_whats_my_order_follows_each_move_the_company_makes`|`keep`|Status visto pelo Agent acompanha cada mudança do painel|
|`test_order_the_company_cancelled_is_reported_as_cancelled_to_the_contact`|`keep`|Cancelado pela Company aparece cancelado e não recancela|
|`test_alteration_loses_when_the_company_starts_preparing_between_the_read_and_the_write`|`keep`|Corrida: alteração perde para o preparo iniciado|

#### `tests/packs/test_packs_registry.py`
2 testes: 2 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_restaurant_recebe_o_pack_de_catalogo_e_pedidos_alem_do_nucleo`|`keep`|Restaurant recebe Pack de pedidos mais as tools do núcleo|
|`test_business_type_sem_pack_fica_so_com_as_tools_do_nucleo (×3 casos)`|`keep`|Sem Pack: só tools do núcleo (desconhecido, vazio, nulo)|

#### `tests/scripts/test_create_superuser.py`
9 testes: 9 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_creates_a_superuser_with_a_bcrypt_hash`|`keep`|Cria superusuário ativo com senha hasheada verificável|
|`test_promotes_an_existing_user_without_touching_the_password`|`keep`|Promoção preserva hash e nome existentes|
|`test_promoting_works_without_a_password`|`keep`|Promover usuário existente não exige senha|
|`test_reactivates_an_inactive_user_when_promoting`|`keep`|Usuário inativo volta a ficar ativo ao promover|
|`test_is_idempotent`|`keep`|Segunda execução é `unchanged`, sem duplicar nem rehash|
|`test_creating_requires_a_valid_password_and_email`|`keep`|Rejeita senha ausente/curta e e-mail inválido sem criar|
|`test_cli_reads_email_and_password_from_env_and_never_prints_the_password`|`keep`|CLI lê env e não imprime a senha|
|`test_cli_args_override_env_and_missing_email_fails_without_leaking`|`keep`|E-mail ausente retorna 2 sem vazar senha; args funcionam|
|`test_seed_keeps_dev_user_non_superuser_unless_opted_in`|`keep`|Usuário dev só vira superuser com `SEED_DEV_SUPERUSER=1`|

#### `tests/scripts/test_seed_company_agents.py`
6 testes: 6 keep.

| Teste | Categoria | Motivo / equivalente |
|---|---|---|
|`test_each_company_gets_one_agent_and_its_instances_are_bound_to_it`|`keep`|Um Agent por Company, instâncias ligadas e habilitadas|
|`test_running_twice_does_not_duplicate_agents`|`keep`|Seed idempotente, sem Agents duplicados|
|`test_instance_without_company_stays_unbound`|`keep`|Instância órfã não ganha Agent nem é habilitada|
|`test_existing_binding_to_another_agent_is_kept`|`keep`|Vínculo manual existente não é sobrescrito|
|`test_rerunning_the_seed_does_not_reenable_an_instance_the_operator_disabled`|`keep`|Seed não reabilita instância desligada pelo operador|
|`test_agent_is_owned_by_a_user_of_the_company_when_there_is_one`|`keep`|`owner_id` do Agent é usuário da Company|
