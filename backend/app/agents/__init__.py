"""
WhatsApp Agent Package
Intelligent agent for WhatsApp customer service using LangGraph.
"""

__all__ = ["WhatsAppAgent"]


def __getattr__(name):
    if name == "WhatsAppAgent":
        from app.agents.agent_executor import WhatsAppAgent

        return WhatsAppAgent
    raise AttributeError(f"module 'app.agents' has no attribute {name!r}")
