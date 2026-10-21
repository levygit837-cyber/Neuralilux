# Um único Agent: super agent, Sales/SAC, RAG e Qdrant removidos

O produto tem um Agent de atendimento por Company, com 7 Tools. O super agent (chat interno com 21 Tools e inventário), o roteamento Sales/SAC, o RAG de documentos e o Qdrant foram removidos com suas tabelas. Nenhum tinha uso real nos dados, e cada um multiplicava prompts, Tools e caminhos de erro. Se um assistente interno voltar, ele entra como outro consumidor do mesmo loop, não como um segundo framework.
