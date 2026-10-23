"""Rotas de Instances, divididas por assunto; `router` junta as partes sem prefixo."""
from fastapi import APIRouter

from app.api.routes.instances import agent, connection, state

router = APIRouter()
router.include_router(state.router)
router.include_router(connection.router)
router.include_router(agent.router)
