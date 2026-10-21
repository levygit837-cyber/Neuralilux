from fastapi import APIRouter
from app.api.routes import (
    agents,
    auth,
    companies,
    conversations,
    dashboard,
    gateways,
    instances,
    menu,
    messages,
    products,
    tickets,
    webhooks,
    whatsapp,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(menu.router, prefix="/menu", tags=["menu"])
api_router.include_router(instances.router, prefix="/instances", tags=["instances"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(whatsapp.router, prefix="/whatsapp", tags=["whatsapp"])
api_router.include_router(
    conversations.router, prefix="", tags=["conversations", "contacts"]
)
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(gateways.router, prefix="/gateways", tags=["gateways"])
