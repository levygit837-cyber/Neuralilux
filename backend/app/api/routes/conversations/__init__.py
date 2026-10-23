"""Rotas de Conversations, Contacts e Handoff; `router` junta as partes sem prefixo."""
from fastapi import APIRouter

from app.api.routes.conversations import chat_state, contacts, human_control, listing

router = APIRouter()
# `chat_state` primeiro: `/conversations/counts` e `/conversations/sync` não podem ser lidos como um id.
router.include_router(chat_state.router)
router.include_router(listing.router)
router.include_router(contacts.router)
router.include_router(human_control.router)
