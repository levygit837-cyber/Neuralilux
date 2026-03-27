from fastapi import APIRouter
from app.api.v1.endpoints import auth, instances, agents, messages, webhooks, companies, products, whatsapp, conversations

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(instances.router, prefix="/instances", tags=["instances"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
api_router.include_router(conversations.router, prefix="", tags=["conversations", "contacts"])
