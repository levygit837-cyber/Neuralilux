# Loop de agente próprio, sem LangChain/LangGraph

O Agent roda num loop próprio em `backend/app/agent/loop.py`: chama o modelo, executa os `tool_use` em ordem, devolve os `tool_result` e repete até `end_turn`, uma Tool com `ends_turn` ou `max_steps`. LangChain e LangGraph eram usados só como `.invoke()` e um grafo de seis nós com uma única aresta condicional, e traziam cinco pacotes fixados e uma camada de compatibilidade. Um loop curto, próprio, é mais fácil de testar com um cliente falso e de depurar do que o grafo.

## Considered Options

- Manter LangGraph: rejeitado, o grafo era quase linear e o estado tinha campos lidos antes de carregados (bug do Handoff).
- Usar o SDK `anthropic`: rejeitado, só precisamos de `POST /v1/messages` e o Gateway não é a API oficial.
