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
]
