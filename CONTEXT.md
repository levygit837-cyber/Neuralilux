# Neuralilux

Agente de atendimento por WhatsApp com IA, configurável para qualquer negócio. Uma Company conecta seu número, o Agent atende os Contacts usando as Tools do Pack do seu ramo e passa para um humano quando precisa.

## Language

### Tenancy e canal

**Company**:
O negócio que usa o Neuralilux (restaurante, farmácia, loja, academia). Dona dos dados de catálogo, pedidos e configuração.
_Avoid_: Tenant, empresa cliente, loja

**Business Type**:
O ramo da Company. Decide qual Pack o Agent usa.
_Avoid_: Segmento, categoria de empresa

**Instance**:
Um número de WhatsApp conectado via Evolution API e vinculado a uma Company.
_Avoid_: Conexão, bot

**Contact**:
A pessoa do outro lado do WhatsApp, identificada pelo número dentro de uma Instance.
_Avoid_: Cliente, usuário, lead

**Conversation**:
O fio de mensagens entre uma Instance e um Contact.
_Avoid_: Chat, thread

**Message**:
Uma unidade de texto ou mídia numa Conversation, enviada pelo Contact, pelo Agent ou por um Attendant.
_Avoid_: Mensagem de chat, evento

**Session**:
Um trecho contínuo de uma Conversation. Começa na primeira Message do Contact depois de um tempo sem Messages (configurável por Company, padrão 3 h); pausas menores continuam a mesma. A Recent Window mostra só a Session atual, e um Order aberto na anterior vira `abandoned`.
_Avoid_: Sessão de login, sessão do WhatsApp
_Também dito_: "atendimento" ("novo atendimento"), só em prosa informal e nos prompts do Agent

### Agente

**Agent**:
O atendente de IA de uma Company. Existe um por Company.
_Avoid_: Bot, assistente, super agent, sales agent, SAC agent

**Turn**:
O ciclo em que o Agent recebe as Messages que o Contact mandou numa rajada (agrupadas por uma pausa curta), pensa, chama Tools e produz no máximo uma resposta.
_Avoid_: Execução, run, invocação

**Tool**:
Uma capacidade nomeada que o Agent pode chamar durante um Turn, com argumentos em JSON.
_Avoid_: Função, skill, ação

**Pack**:
O conjunto de Tools e instruções de um Business Type. "Catálogo & pedidos" é o primeiro.
_Avoid_: Plugin, módulo de negócio, vertical

**Gateway**:
Um endpoint de inferência que fala o protocolo Anthropic Messages e serve os modelos que o Agent usa.
_Avoid_: Provider, LLM, backend de IA

### Memória

**Recent Window**:
As últimas Messages da Session atual que o Agent vê literalmente em cada Turn.
_Avoid_: Contexto, buffer

**Summary**:
O resumo acumulado das Messages de uma Conversation que já saíram da Recent Window.
_Avoid_: Memória longa, digest

**History Search**:
A busca textual que o Agent faz nas Messages antigas de um Contact.
_Avoid_: RAG, busca semântica, retrieval

### Atendimento humano

**Handoff**:
A passagem da Conversation do Agent para um Attendant. Enquanto vale, o Agent não responde.
_Avoid_: Escalonamento, transbordo, human in the loop

**Attendant**:
A pessoa da Company que atende a Conversation depois do Handoff.
_Avoid_: Operador, humano, agente humano

**Ticket**:
O registro do motivo de um Handoff, aberto para o Attendant resolver. Termina `closed` (o Attendant devolveu a Conversation ao Agent) ou `expired` (ninguém atendeu dentro do prazo da Company).
_Avoid_: Chamado, protocolo, caso

### Catálogo & pedidos

**Catalog Item**:
Um produto ou serviço que a Company oferece, com preço e disponibilidade.
_Avoid_: Produto, item de menu, SKU

**Order**:
O pedido que o Contact monta e confirma na Conversation. Só fecha depois que o Contact vê a Recap e confirma numa Message posterior, e a Company fechada recusa o fechamento. Fica `abandoned` se a Session acaba com ele aberto; nunca é retomado sozinho, o Agent só recria um Order novo a partir dele se o Contact pedir.
_Avoid_: Compra, carrinho, venda

**Recap** (Recapitulação):
O resumo de itens, entrega, pagamento e total que o Contact precisa ver e confirmar, numa Message posterior, antes de o Order fechar. Só vale depois que a resposta que a traz foi enviada; qualquer alteração no Order depois dela, ou um Turn que falhe antes do envio, a invalida e exige uma nova.
_Avoid_: Resumo do pedido, confirmação (é a resposta do Contact à Recap, não a Recap), checkout

**Delivery Zone**:
Uma área de entrega da Company com sua taxa.
_Avoid_: Região, bairro, faixa de CEP

**Payment Record**:
A cobrança gerada para um Order, como um Pix com valor e identificador.
_Avoid_: Pagamento, transação, fatura
