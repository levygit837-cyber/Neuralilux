"""Rotas de Instances, divididas por assunto; `router` junta as duas partes sem prefixo."""
from fastapi import APIRouter

from app.api.routes.instances import agent, connection

router = APIRouter()
router.include_router(connection.router)
router.include_router(agent.router)
