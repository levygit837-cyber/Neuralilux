"""Rotas de Conversations, Contacts e Handoff; `router` junta as partes sem prefixo."""
from fastapi import APIRouter

from app.api.routes.conversations import contacts, conversations, human_control

router = APIRouter()
router.include_router(conversations.router)
router.include_router(contacts.router)
router.include_router(human_control.router)
