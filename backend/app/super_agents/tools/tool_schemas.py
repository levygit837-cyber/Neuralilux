"""OpenAI-format tool definitions for the Super Agent native tool calling."""
from __future__ import annotations

from typing import Any, Dict, List

SUPER_AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "whatsapp_list_contacts",
            "description": (
                "Lista os contatos da empresa no WhatsApp. "
                "Use para descobrir quais contatos existem antes de enviar mensagens ou ler conversas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Filtro de busca por nome, número ou JID. Deixe vazio para listar todos.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de contatos a retornar (padrão 20, máximo 50).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_resolve_contacts",
            "description": (
                "Busca contatos pelo nome ou número para encontrar o remote_jid exato. "
                "Use ANTES de enviar mensagem ou ler conversa de um contato específico."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nome, número de telefone ou parte do nome do contato.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados (padrão 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_read_messages",
            "description": (
                "Lê as mensagens recentes de uma conversa WhatsApp. "
                "Requer instance_name e remote_jid (obtenha via whatsapp_resolve_contacts primeiro)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "instance_name": {
                        "type": "string",
                        "description": "Nome da instância WhatsApp.",
                    },
                    "remote_jid": {
                        "type": "string",
                        "description": "JID do contato (ex: 5511999999999@s.whatsapp.net).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Número máximo de mensagens (padrão 20, máximo 50).",
                    },
                },
                "required": ["instance_name", "remote_jid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_send_message",
            "description": (
                "Envia uma mensagem de texto para um contato específico no WhatsApp. "
                "Requer instance_name e remote_jid (obtenha via whatsapp_resolve_contacts). "
                "IMPORTANTE: sempre confirme com o usuário antes de enviar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "instance_name": {
                        "type": "string",
                        "description": "Nome da instância WhatsApp.",
                    },
                    "remote_jid": {
                        "type": "string",
                        "description": "JID do destinatário.",
                    },
                    "message": {
                        "type": "string",
                        "description": "Texto da mensagem a ser enviada.",
                    },
                },
                "required": ["instance_name", "remote_jid", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_send_bulk",
            "description": (
                "Envia mensagem em massa para múltiplos contatos. "
                "Recebe uma lista de destinatários com instance_name e remote_jid de cada um. "
                "IMPORTANTE: SEMPRE liste e confirme com o usuário antes de executar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "recipients": {
                        "type": "array",
                        "description": "Lista de destinatários. Cada item deve ter instance_name e remote_jid.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "instance_name": {"type": "string"},
                                "remote_jid": {"type": "string"},
                                "display_name": {"type": "string"},
                            },
                            "required": ["instance_name", "remote_jid"],
                        },
                    },
                    "message": {
                        "type": "string",
                        "description": "Texto da mensagem a ser enviada para todos os destinatários.",
                    },
                },
                "required": ["recipients", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "database_query",
            "description": (
                "Consulta dados da empresa no banco de dados (somente leitura). "
                "Use para buscar produtos, contatos, conversas, instâncias e estatísticas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Tabela a consultar.",
                        "enum": [
                            "products",
                            "contacts",
                            "conversations",
                            "messages",
                            "instances",
                            "company",
                        ],
                    },
                    "query_type": {
                        "type": "string",
                        "description": "Tipo de consulta.",
                        "enum": ["list", "count", "search", "aggregate"],
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filtros opcionais. Use {\"q\": \"termo\"} para buscas textuais.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados (padrão 10, máximo 100).",
                    },
                },
                "required": ["table", "query_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "menu_lookup",
            "description": (
                "Consulta o cardápio/catálogo de produtos da empresa. "
                "Pode filtrar por categoria ou buscar por nome do item."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca para itens do cardápio.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Nome da categoria para filtrar.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de itens (padrão 8, máximo 25).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Busca informações públicas na internet via DuckDuckGo. "
                "Use para consultar preços, notícias, informações de concorrentes, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca na internet.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Máximo de resultados (padrão 5, máximo 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": (
                "Faz fetch do conteúdo de uma URL pública. "
                "Use para ler páginas web, APIs públicas ou documentos online."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL pública completa (http ou https).",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_store",
            "description": (
                "Armazena informação na base de conhecimento para uso futuro. "
                "Use quando o usuário pedir para anotar, lembrar ou salvar algo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Identificador curto do conhecimento (ex: 'preferência cliente João').",
                    },
                    "value": {
                        "type": "string",
                        "description": "Conteúdo completo a ser armazenado.",
                    },
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledge_search",
            "description": (
                "Busca conhecimento previamente armazenado na base de conhecimento."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca para encontrar conhecimento salvo.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "document_create",
            "description": (
                "Cria um documento (PDF, TXT, JSON ou Markdown). "
                "Use quando o usuário pedir para gerar relatórios, documentos ou exportar dados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_type": {
                        "type": "string",
                        "description": "Tipo do documento.",
                        "enum": ["pdf", "txt", "json", "markdown"],
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo do documento.",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo (sem extensão). Padrão: 'documento-super-agent'.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição opcional do documento.",
                    },
                },
                "required": ["file_type", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_list_product_categories",
            "description": (
                "Lista todas as categorias de produtos do catálogo ativo da empresa. "
                "Use para descobrir quais categorias existem antes de listar ou criar produtos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de categorias a retornar (padrão 50).",
                    },
                },
                "required": ["company_id", "user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_list_products_by_category",
            "description": (
                "Lista todos os produtos de uma categoria específica. "
                "Use para ver quais produtos existem em uma categoria."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "category_id": {
                        "type": "string",
                        "description": "ID da categoria.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de produtos a retornar (padrão 20).",
                    },
                },
                "required": ["company_id", "user_id", "category_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_search_product_in_category",
            "description": (
                "Busca um produto por nome em uma categoria específica. "
                "Use para encontrar um produto específico pelo nome."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "category_id": {
                        "type": "string",
                        "description": "ID da categoria.",
                    },
                    "product_name": {
                        "type": "string",
                        "description": "Nome do produto para buscar.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados (padrão 10).",
                    },
                },
                "required": ["company_id", "user_id", "category_id", "product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_create_product_category",
            "description": (
                "Cria uma nova categoria de produtos. "
                "Use quando o usuário pedir para criar uma nova categoria no catálogo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nome da categoria.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição opcional da categoria.",
                    },
                },
                "required": ["company_id", "user_id", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_create_product",
            "description": (
                "Cria um novo produto em uma categoria. "
                "Use quando o usuário pedir para adicionar um novo produto ao catálogo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "category_id": {
                        "type": "string",
                        "description": "ID da categoria onde o produto será criado.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nome do produto.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição opcional do produto.",
                    },
                    "price": {
                        "type": "number",
                        "description": "Preço do produto.",
                    },
                    "sku": {
                        "type": "string",
                        "description": "SKU único do produto (opcional).",
                    },
                    "stock_quantity": {
                        "type": "integer",
                        "description": "Quantidade em estoque (padrão 0).",
                    },
                    "is_available": {
                        "type": "boolean",
                        "description": "Disponibilidade do produto (padrão true).",
                    },
                    "image_url": {
                        "type": "string",
                        "description": "URL da imagem do produto (opcional).",
                    },
                },
                "required": ["company_id", "user_id", "category_id", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_update_product",
            "description": (
                "Edita um produto existente. "
                "Use quando o usuário pedir para modificar um produto do catálogo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "product_id": {
                        "type": "string",
                        "description": "ID do produto a ser editado.",
                    },
                    "category_id": {
                        "type": "string",
                        "description": "Nova categoria do produto (opcional).",
                    },
                    "name": {
                        "type": "string",
                        "description": "Novo nome do produto (opcional).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Nova descrição do produto (opcional).",
                    },
                    "price": {
                        "type": "number",
                        "description": "Novo preço do produto (opcional).",
                    },
                    "sku": {
                        "type": "string",
                        "description": "Novo SKU do produto (opcional).",
                    },
                    "stock_quantity": {
                        "type": "integer",
                        "description": "Nova quantidade em estoque (opcional).",
                    },
                    "is_available": {
                        "type": "boolean",
                        "description": "Nova disponibilidade do produto (opcional).",
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Nova URL da imagem do produto (opcional).",
                    },
                },
                "required": ["company_id", "user_id", "product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_delete_product_category",
            "description": (
                "Exclui uma categoria e todos os seus produtos. "
                "Use quando o usuário pedir para remover uma categoria do catálogo. "
                "Não permite exclusão se houver produtos com estoque > 0."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "category_id": {
                        "type": "string",
                        "description": "ID da categoria a ser excluída.",
                    },
                },
                "required": ["company_id", "user_id", "category_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inventory_delete_product",
            "description": (
                "Exclui um produto do catálogo. "
                "Use quando o usuário pedir para remover um produto. "
                "Não permite exclusão se o produto tiver estoque > 0."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company_id": {
                        "type": "string",
                        "description": "ID da empresa.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "ID do usuário solicitante.",
                    },
                    "product_id": {
                        "type": "string",
                        "description": "ID do produto a ser excluído.",
                    },
                },
                "required": ["company_id", "user_id", "product_id"],
            },
        },
    },
]
