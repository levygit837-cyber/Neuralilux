"""Respostas das rotas de estado da lista de chats (`/conversations/counts`, `/sync`, `/{id}/read`)."""
from pydantic import BaseModel


class ConversationCounts(BaseModel):
    all: int
    unread: int
    groups: int
    ai: int
    human: int
    unread_messages: int


class ConversationSyncResult(BaseModel):
    conversations: int
    messages: int


class UnreadReset(BaseModel):
    unread_count: int
