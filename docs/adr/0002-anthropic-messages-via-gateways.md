# Inferência só via Gateways no protocolo Anthropic Messages

Todo modelo é acessado por um Gateway cadastrado que fala `POST {base_url}/v1/messages`, com cliente httpx próprio. Gemini, Vertex, LM Studio e o caminho OpenAI foram removidos. Um protocolo só elimina três clientes e os fallbacks entre eles; o formato Messages tem `tool_use`/`tool_result` nativos, que é o que o loop precisa.

## Consequences

- Gateways são globais, não por Company. Por isso criar, editar, apagar e testar Gateway exige superuser: `base_url` é um alvo de SSRF.
- Um modelo que só fale OpenAI precisa de um Gateway que traduza para Messages.
