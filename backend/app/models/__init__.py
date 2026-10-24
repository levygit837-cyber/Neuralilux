"""Modelos ORM agrupados por agregado.

Importar este pacote registra todas as tabelas em `Base.metadata` (o Alembic e os relationships
por nome dependem disso). Código novo importa daqui: `from app.models import Company`.
"""
from app.models.agent import Agent
from app.models.base import generate_uuid
from app.models.catalog import MenuCatalog, MenuCategory, MenuItem
from app.models.company import BusinessType, Company
from app.models.contact import Contact
from app.models.conversation import Conversation, ConversationMemorySummary
from app.models.gateway import GatewayAssignment, GatewayModel, InferenceGateway
from app.models.instance import Instance, InstanceStatus
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.order import CustomerOrder, CustomerOrderItem, DeliveryZone, PaymentRecord
from app.models.ticket import Ticket
from app.models.user import User

__all__ = [
    "Agent",
    "BusinessType",
    "Company",
    "Contact",
    "Conversation",
    "ConversationMemorySummary",
    "CustomerOrder",
    "CustomerOrderItem",
    "DeliveryZone",
    "GatewayAssignment",
    "GatewayModel",
    "InferenceGateway",
    "Instance",
    "InstanceStatus",
    "MenuCatalog",
    "MenuCategory",
    "MenuItem",
    "Message",
    "MessageDirection",
    "MessageStatus",
    "MessageType",
    "PaymentRecord",
    "Ticket",
    "User",
    "generate_uuid",
]
