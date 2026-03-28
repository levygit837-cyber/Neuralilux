"""
Tool Definitions - Gemini Function Calling format for WhatsApp Agent tools.
"""

from typing import List, Dict, Any


CARDAPIO_TOOL_DEFINITION = {
    "name": "cardapio_tool",
    "description": "Consulta o cardápio estruturado da Macedos. Use para listar categorias, buscar itens por categoria, buscar itens específicos ou mostrar o cardápio completo.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Consulta sobre o cardápio. Exemplos: 'listar_categorias', 'categoria:Pizzas', 'buscar:Margherita', 'listar_todos'"
            }
        },
        "required": ["query"]
    }
}

PEDIDO_TOOL_DEFINITION = {
    "name": "pedido_tool",
    "description": "Gerencia o pedido do cliente. Use para adicionar, remover, consultar ou finalizar pedidos.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["adicionar", "remover", "consultar", "limpar", "total", "iniciar_finalizacao", "confirmar"],
                "description": "Ação a ser executada no pedido"
            },
            "item_nome": {
                "type": "string",
                "description": "Nome do item (para adicionar/remover)"
            },
            "quantidade": {
                "type": "integer",
                "description": "Quantidade do item (para adicionar)"
            },
            "observacao": {
                "type": "string",
                "description": "Observação sobre o item (opcional)"
            }
        },
        "required": ["action"]
    }
}

HORARIO_TOOL_DEFINITION = {
    "name": "horario_tool",
    "description": "Verifica o horário de funcionamento da Macedos.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": []
    }
}

WHATSAPP_AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "function_declarations": [
            {
                "name": "cardapio_tool",
                "description": "Consulta o cardápio estruturado da Macedos. Use para listar categorias, buscar itens por categoria, buscar itens específicos ou mostrar o cardápio completo.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "Consulta sobre o cardápio. Exemplos: 'listar_categorias', 'categoria:Pizzas', 'buscar:Margherita', 'listar_todos'"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "pedido_tool",
                "description": "Gerencia o pedido do cliente. Use para adicionar, remover, consultar ou finalizar pedidos.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "action": {
                            "type": "STRING",
                            "enum": ["adicionar", "remover", "consultar", "limpar", "total", "iniciar_finalizacao", "confirmar"],
                            "description": "Ação a ser executada no pedido"
                        },
                        "item_nome": {
                            "type": "STRING",
                            "description": "Nome do item (para adicionar/remover)"
                        },
                        "quantidade": {
                            "type": "INTEGER",
                            "description": "Quantidade do item (para adicionar)"
                        },
                        "observacao": {
                            "type": "STRING",
                            "description": "Observação sobre o item (opcional)"
                        }
                    },
                    "required": ["action"]
                }
            },
            {
                "name": "horario_tool",
                "description": "Verifica o horário de funcionamento da Macedos.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                    "required": []
                }
            }
        ]
    }
]
