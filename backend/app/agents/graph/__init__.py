"""
Graph - LangGraph definitions for the WhatsApp agent.
"""

__all__ = ["create_whatsapp_graph", "WhatsAppAgentGraph"]


def __getattr__(name):
    if name in {"create_whatsapp_graph", "WhatsAppAgentGraph"}:
        from app.agents.graph.whatsapp_graph import create_whatsapp_graph, WhatsAppAgentGraph

        return {
            "create_whatsapp_graph": create_whatsapp_graph,
            "WhatsAppAgentGraph": WhatsAppAgentGraph,
        }[name]
    raise AttributeError(f"module 'app.agents.graph' has no attribute {name!r}")
