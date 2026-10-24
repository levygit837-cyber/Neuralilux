# Integrar um sistema de gestão

Há dois sentidos de integração. Em um, o sistema de gestão (ERP, PDV, agenda) **empurra** dados para o Neuralilux pela API REST. No outro, o Agent **puxa** dados e executa ações no sistema durante um Turn, por Tools de um Pack. Termos conforme o [glossário](../CONTEXT.md); a estrutura do Pack está em [packs.md](packs.md).

| Preciso de… | Use |
|---|---|
| Manter cardápio, preços e disponibilidade em dia | [API REST](#via-api-rest) |
| Ler Conversations, Tickets e Messages para um painel externo | [API REST](#via-api-rest) |
| O Agent consultar estoque, agenda ou preço em tempo real | [Tool de Pack](#via-tools-de-pack) |
| O Agent gravar um pedido ou agendamento no sistema da Company | [Tool de Pack](#via-tools-de-pack) |

## Via API REST

Base: `http://<host>:8000/api/v1`. A documentação interativa (`/docs` e `/redoc`) só existe com `ENVIRONMENT=development`; fora disso responde 404. O schema completo continua em `/openapi.json`.

### Autenticação

Toda rota de dados exige `Authorization: Bearer <JWT>`. (O painel no navegador usa o mesmo JWT num cookie `httpOnly`, [ADR 0008](adr/0008-sessao-em-cookie-httponly.md); quando os dois vêm, o Bearer vale. Integrações de servidor usam o Bearer e não precisam do cookie.) O login é um formulário (`application/x-www-form-urlencoded`), não JSON:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d 'username=integracao@empresa.com' -d 'password=...'
# {"access_token": "...", "token_type": "bearer"}
```

- O token expira em `ACCESS_TOKEN_EXPIRE_MINUTES` (padrão 30). Uma integração de servidor tem de refazer o login ao receber 401.
- O 401 vale também para token adulterado, `sub` que não existe mais e **usuário desativado**: o token só abre a API (e o Socket.IO) enquanto o usuário existir e estiver ativo, mesmo antes de vencer. O JWT é HS256 assinado com `SECRET_KEY` (biblioteca PyJWT).
- `POST /auth/register`: e-mail já cadastrado responde 409 (também quando dois cadastros chegam juntos) e `company_id` inexistente responde 422. Erro inesperado responde 500 com mensagem genérica; o detalhe fica só no log do servidor, em nenhuma rota o texto da exceção vai para o `detail`.
- **Cadastro público fechado por padrão.** Sem `ALLOW_PUBLIC_REGISTRATION=true`, `POST /auth/register` anônimo (ou de usuário comum) responde 403; só um superusuário autenticado cadastra. Aberto, o registro público só cria usuário **sem** Company, e `company_id` continua exigindo superusuário.
- **Rate limit por IP** em `/auth/login` e `/auth/register`: acima do limite, 429 com `Retry-After` (segundos até a janela virar). Cada tentativa conta, certa ou errada, e quem está bloqueado nem tem a senha conferida. Redis fora do ar: 503 (falha fechada). Superusuário autenticado não é limitado no cadastro. Uma integração de servidor deve reusar o token até o 401 em vez de logar a cada chamada. Valores e proxy confiável em [operations.md](operations.md#login-ou-cadastro-respondem-429-ou-503).
- **Não há chave de API para máquinas.** A integração usa um usuário comum da Company, criado por um superusuário (`POST /auth/register` com `company_id` exige um superusuário autenticado) ou por `scripts/create_superuser.py`. Use um usuário dedicado, com senha forte guardada no cofre do sistema de gestão, nunca a conta de uma pessoa.
- O escopo da Company vem do usuário: as rotas de `/menu` operam sobre `current_user.company_id`.
- O escopo das Instances vem do dono: `/instances`, `/conversations`, `/contacts`, `/dashboard`, `/tickets` e `/orders` só alcançam as Instances do usuário (`Instance.owner_id`); o superusuário alcança todas. Instance de outro dono responde 403 em `/instances`; Ticket fora do escopo responde 404.

### Rotas úteis

| Rota | Uso |
|---|---|
| `GET /menu` | Cardápio ativo da Company: catálogo, categorias e Catalog Items. |
| `POST /menu/categories`, `PATCH`/`DELETE /menu/categories/{id}` | Categorias. |
| `POST /menu/items`, `PATCH`/`DELETE /menu/items/{id}` | Catalog Items: `name`, `price`, `is_available`, `sku`, `stock_quantity`, `category_id`. |
| `GET /companies/{id}`, `PUT /companies/{id}` | Configuração da Company, veja [agent.md](agent.md#configuração-da-company). Só a Company do usuário (outra: 403) ou superusuário. |
| `GET /companies/{id}/agent`, `PUT /companies/{id}/agent` | Temperatura e `max_tokens` do Agent da Company. Mesma regra de acesso. |
| `POST /companies/`, `DELETE /companies/{id}` | Criar e desativar uma Company. Só superusuário (403 para os demais, inclusive o dono). |
| `GET /conversations`, `GET /conversations/{id}/messages` | Conversations e Messages. |
| `POST /conversations/{id}/messages` | Envia texto pela Instance (a Instance precisa estar `connected`). |
| `POST /conversations/{id}/take-control`, `POST .../release-control`, `GET .../human-control-status` | Assumir, devolver ao Agent (fecha o Ticket) e consultar o Handoff, veja [operations.md](operations.md#handoff-e-tickets). |
| `GET /tickets`, `GET /tickets/{id}` | Tickets de Handoff (só leitura; assumir e devolver são `take-control`/`release-control` da Conversation). |
| `GET /orders`, `POST /orders/{id}/status` | Painel de Pedidos da Company: lista e muda o status (recebido, em preparo, saiu para entrega, entregue, cancelado); o Contact é avisado no WhatsApp. Veja [operations.md](operations.md#painel-de-pedidos-status-pela-company). |
| `GET /orders/refunds`, `POST /orders/refunds/{id}/refunded`, `POST /orders/refunds/{id}/dismissed` | Estornos Pix abertos (Order cancelado ou alterado) e a baixa manual idempotente, veja [operations.md](operations.md#cancelamento-alteração-e-estorno-de-pix). |
| `GET /instances/`, `POST /instances/{nome}`, `GET .../status`, `POST .../connect`, `DELETE .../logout`, `DELETE /instances/{nome}` | Instances do usuário e conexão com a Evolution (login obrigatório; a listagem não devolve o token da Evolution). Só o `POST` cria a Instance local, com a Company do usuário. |

### Exemplo: sincronizar a disponibilidade de um Catalog Item

```bash
TOKEN=...   # do login acima
curl -s -X PATCH "http://localhost:8000/api/v1/menu/items/$ITEM_ID" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"is_available": false, "stock_quantity": 0}'
```

A Tool `buscar_cardapio` só devolve itens disponíveis, então a mudança vale já no próximo Turn.

Item com horário próprio (ex.: pizza só à noite) não some fora da janela. O JSON do cardápio traz as janelas em `items_availability` (`weekday` 1 = domingo a 7 = sábado, `period_end` inclusivo; fim antes do início cruza a meia-noite, as mesmas regras de `business_hours`) e marca `is_available=false` no item que estava fora da janela na hora da captura (`source.fetched_at_utc`). O sync (`app/services/menu/availability.py`) lê esse horário no fuso da Company: se a captura caiu fora da janela, o `false` é só do horário e o item é gravado disponível; se caiu dentro (item pausado ou esgotado) ou o JSON não traz o horário da captura, o `false` vale. Na busca, fora da janela o item volta com `disponibilidade` ("Fora do horário agora; disponível a partir de hoje às 18:00.") e o Agent diz que existe e quando pode ser pedido.

### Eventos para o sistema de gestão

Não há webhook de saída do Neuralilux. O que existe:

- **Socket.IO** (`/realtime/socket.io`, JWT em `auth.token`): `new_message`, `conversation_updated`, `tool_event`, `human_handoff_requested` e outros, descritos em [agent.md](agent.md#eventos-em-tempo-real).
- **Polling** de `GET /tickets?status=open` para reagir a Handoffs.

O endpoint `/webhooks/evolution` é exclusivo da Evolution ([ADR 0006](adr/0006-webhook-token-auth.md)); não o use como entrada de sistemas externos.

### Limites atuais

- Não há rate limit por integração nem chave de API revogável.

## Via Tools de Pack

Quando o Agent precisa de dado vivo ou de gravar no sistema da Company, a integração é uma Tool: o handler chama a API do sistema de gestão durante o Turn. Isso mantém o núcleo genérico ([ADR 0004](adr/0004-generic-core-business-packs.md)); o conhecimento do sistema externo vive só no Pack.

Exemplo, só como documentação: uma Tool `consultar_horarios` do Pack de academia (veja [packs.md](packs.md#exemplo-pack-de-academia)) consulta a agenda no sistema de gestão por HTTP.

```python
# backend/app/packs/gym/agenda.py
from __future__ import annotations

import json
from typing import Any

import httpx
import structlog

from app.agent.contracts import Tool, ToolContext, ToolResult
from app.core.config import settings

logger = structlog.get_logger()

AGENDA_TIMEOUT_SECONDS = 5.0


async def _consultar_horarios(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    # GYM_AGENDA_URL e GYM_AGENDA_TOKEN seriam novos campos em Settings (app/core/config.py).
    try:
        async with httpx.AsyncClient(timeout=AGENDA_TIMEOUT_SECONDS) as client:
            response = await client.get(
                f"{settings.GYM_AGENDA_URL}/aulas",
                params={"modalidade": args["modalidade"], "dia": args["dia"]},
                headers={"Authorization": f"Bearer {settings.GYM_AGENDA_TOKEN}"},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        # Erro esperado de integração: o modelo recebe uma orientação, não uma exceção.
        logger.warning("Agenda indisponível", company_id=ctx.company_id, exc_info=True)
        return ToolResult(
            content=json.dumps(
                {"erro": "A agenda está indisponível agora. Ofereça um atendente."}, ensure_ascii=False
            ),
            is_error=True,
        )
    return ToolResult(content=json.dumps({"aulas": response.json()}, ensure_ascii=False))


def consultar_horarios_tool() -> Tool:
    return Tool(
        name="consultar_horarios",
        description="Horários das aulas de uma modalidade em um dia da semana. Use antes de informar qualquer horário.",
        input_schema={
            "type": "object",
            "properties": {
                "modalidade": {"type": "string", "description": "Ex: 'spinning'."},
                "dia": {"type": "string", "description": "Dia da semana, ex: 'segunda'."},
            },
            "required": ["modalidade", "dia"],
            "additionalProperties": False,
        },
        handler=_consultar_horarios,
    )
```

Regras para Tools que chamam sistemas externos:

- **Timeout curto e explícito.** O Turn inteiro tem `max_steps` chamadas ao modelo e o Contact está esperando; 5 s por chamada externa é um teto razoável.
- **Sem retry dentro da Tool.** Uma falha vira `ToolResult(is_error=True)` com orientação. O prompt base já manda o Agent não repetir a mesma chamada e oferecer um atendente.
- **Escopo pela Company.** Se o sistema externo atende várias Companies, escolha credencial e Company por `ctx.company_id`, nunca por um valor que o modelo informou.
- **Segredos fora do código.** Credenciais do sistema externo entram por `Settings`/variável de ambiente; se forem por Company, guarde criptografadas como as chaves de Gateway (`app/core/crypto.py`).
- **Ações que gravam** (pedido, agendamento) devem validar tudo antes de enviar e ser idempotentes no sistema externo: o modelo pode chamar a Tool de novo após um erro.
- **Não devolva dados em excesso.** O resultado entra no contexto do modelo; filtre e resuma no handler.
