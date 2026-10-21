# Memória por Conversation: janela, resumo e busca textual, sem vetores

O Agent vê a Recent Window (últimas 20 Messages), o Summary acumulado da Conversation e pode chamar a Tool de History Search, que faz full-text search do Postgres (`portuguese`) nas Messages do Contact. Embeddings em Qdrant foram rejeitados: exigiam um serviço a mais, um modelo de embedding e reindexação, para conversas curtas de atendimento em que o termo exato ("pizza toscana", "pedido de ontem") resolve.
