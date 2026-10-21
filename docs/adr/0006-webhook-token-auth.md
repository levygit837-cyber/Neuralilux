# Webhook da Evolution autenticado por token na query string

`/api/v1/webhooks/evolution*` exige `?token=` igual a `EVOLUTION_WEBHOOK_TOKEN`, comparado em tempo constante. O webhook global da Evolution não garante headers customizados, então o token vai na URL. Instance desconhecida é descartada, nunca criada pelo consumer. Como o token fica na URL, logs de acesso não podem registrar a query string do webhook.
