from fastapi import APIRouter
from app.api.v1.endpoints import auth, instances, agents, messages, webhooks

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(instances.router, prefix="/instances", tags=["instances"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
