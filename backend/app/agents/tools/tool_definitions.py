"""
Tool Definitions - Gemini Function Calling format for WhatsApp Agent tools.
"""

from typing import List, Dict, Any

# Importar as ferramentas existentes
from app.agents.tools.cardapio_tool import cardapio_tool
from app.agents.tools.pedido_tool import pedido_tool
from app.agents.tools.delivery_tool import delivery_tool
from app.agents.tools.horario_tool import horario_tool

# Importar as novas ferramentas
from app.agents.tools.create_payment_tool import create_payment_tool
from app.agents.tools.open_ticket_tool import open_ticket_with_context
from app.agents.tools.order_status_tool import order_status_tool


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

DELIVERY_TOOL_DEFINITION = {
    "name": "delivery_tool",
    "description": "Consulta e calcula taxas de entrega baseadas em bairro/região. Use para informar taxas de entrega ao cliente.",
    "parameters": {
        "type": "object",
        "properties": {
            "acao": {
                "type": "string",
                "enum": ["consultar_taxa", "listar_regioes", "listar_bairros"],
                "description": "Ação a executar: consultar_taxa (para um bairro específico), listar_regioes (todas as zonas), listar_bairros (todos os bairros atendidos)"
            },
            "bairro": {
                "type": "string",
                "description": "Nome do bairro (obrigatório para consultar_taxa)"
            },
            "valor_pedido": {
                "type": "number",
                "description": "Valor total do pedido (opcional, para verificar valor mínimo de entrega)"
            }
        },
        "required": ["acao"]
    }
}

CREATE_PAYMENT_TOOL_DEFINITION = {
    "name": "create_payment_tool",
    "description": "Gera QR Code Pix para pagamento de um pedido. Use quando o cliente desejar finalizar um pedido e pagar via Pix.",
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "ID do pedido a ser pago"
            }
        },
        "required": ["order_id"]
    }
}

OPEN_TICKET_TOOL_DEFINITION = {
    "name": "open_ticket_with_context",
    "description": "Abre um ticket para chamar um atendente humano. Use quando o cliente precisar de atendimento humano ou quando não for possível resolver automaticamente.",
    "parameters": {
        "type": "object",
        "properties": {
            "conversation_id": {
                "type": "string",
                "description": "ID da conversa"
            },
            "instance_id": {
                "type": "string",
                "description": "ID da instância WhatsApp"
            },
            "contact_id": {
                "type": "string",
                "description": "ID do contato"
            },
            "agent_type": {
                "type": "string",
                "enum": ["sales", "sac"],
                "description": "Tipo de agente que está criando o ticket"
            },
            "reason": {
                "type": "string",
                "description": "Motivo do ticket (ex: Reclamação, Problema técnico, Dúvida complexa)"
            },
            "content": {
                "type": "string",
                "description": "Conteúdo detalhado da reclamação ou mensagem do usuário"
            }
        },
        "required": ["conversation_id", "instance_id", "contact_id", "agent_type", "reason", "content"]
    }
}

ORDER_STATUS_TOOL_DEFINITION = {
    "name": "order_status_tool",
    "description": "Consulta status do pedido no banco de dados para rastreamento pós-venda. Use quando o cliente perguntar pelo status do pedido após o fechamento.",
    "parameters": {
        "type": "object",
        "properties": {
            "order_number": {
                "type": "string",
                "description": "Número do pedido (opcional, mas recomendado)"
            },
            "conversation_id": {
                "type": "string",
                "description": "ID da conversa (opcional, usado se order_number não for fornecido)"
            }
        },
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
            },
            {
                "name": "delivery_tool",
                "description": "Consulta e calcula taxas de entrega baseadas em bairro/região. Use para informar taxas de entrega ao cliente.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "acao": {
                            "type": "STRING",
                            "enum": ["consultar_taxa", "listar_regioes", "listar_bairros"],
                            "description": "Ação a executar: consultar_taxa (para um bairro específico), listar_regioes (todas as zonas), listar_bairros (todos os bairros atendidos)"
                        },
                        "bairro": {
                            "type": "STRING",
                            "description": "Nome do bairro (obrigatório para consultar_taxa)"
                        },
                        "valor_pedido": {
                            "type": "NUMBER",
                            "description": "Valor total do pedido (opcional, para verificar valor mínimo de entrega)"
                        }
                    },
                    "required": ["acao"]
                }
            }
        ]
    }
]

# Conjunto de ferramentas específico para Sales Agent
SALES_AGENT_TOOLS: List[Dict[str, Any]] = [
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
                "name": "delivery_tool",
                "description": "Consulta e calcula taxas de entrega baseadas em bairro/região. Use para informar taxas de entrega ao cliente.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "acao": {
                            "type": "STRING",
                            "enum": ["consultar_taxa", "listar_regioes", "listar_bairros"],
                            "description": "Ação a executar: consultar_taxa (para um bairro específico), listar_regioes (todas as zonas), listar_bairros (todos os bairros atendidos)"
                        },
                        "bairro": {
                            "type": "STRING",
                            "description": "Nome do bairro (obrigatório para consultar_taxa)"
                        },
                        "valor_pedido": {
                            "type": "NUMBER",
                            "description": "Valor total do pedido (opcional, para verificar valor mínimo de entrega)"
                        }
                    },
                    "required": ["acao"]
                }
            },
            {
                "name": "create_payment_tool",
                "description": "Gera QR Code Pix para pagamento de um pedido. Use quando o cliente desejar finalizar um pedido e pagar via Pix.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "order_id": {
                            "type": "STRING",
                            "description": "ID do pedido a ser pago"
                        }
                    },
                    "required": ["order_id"]
                }
            }
        ]
    }
]

# Conjunto de ferramentas específico para SAC Agent
SAC_AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "function_declarations": [
            {
                "name": "open_ticket_with_context",
                "description": "Abre um ticket para chamar um atendente humano. Use quando o cliente precisar de atendimento humano ou quando não for possível resolver automaticamente.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "conversation_id": {
                            "type": "STRING",
                            "description": "ID da conversa"
                        },
                        "instance_id": {
                            "type": "STRING",
                            "description": "ID da instância WhatsApp"
                        },
                        "contact_id": {
                            "type": "STRING",
                            "description": "ID do contato"
                        },
                        "agent_type": {
                            "type": "STRING",
                            "enum": ["sales", "sac"],
                            "description": "Tipo de agente que está criando o ticket"
                        },
                        "reason": {
                            "type": "STRING",
                            "description": "Motivo do ticket (ex: Reclamação, Problema técnico, Dúvida complexa)"
                        },
                        "content": {
                            "type": "STRING",
                            "description": "Conteúdo detalhado da reclamação ou mensagem do usuário"
                        }
                    },
                    "required": ["conversation_id", "instance_id", "contact_id", "agent_type", "reason", "content"]
                }
            },
            {
                "name": "order_status_tool",
                "description": "Consulta status do pedido no banco de dados para rastreamento pós-venda. Use quando o cliente perguntar pelo status do pedido após o fechamento.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "order_number": {
                            "type": "STRING",
                            "description": "Número do pedido (opcional, mas recomendado)"
                        },
                        "conversation_id": {
                            "type": "STRING",
                            "description": "ID da conversa (opcional, usado se order_number não for fornecido)"
                        }
                    },
                    "required": []
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
