"""Respostas das rotas de Orders e de estornos Pix (`/orders`)."""
from pydantic import BaseModel


class RefundRow(BaseModel):
    id: str
    order_id: str
    order_number: str
    order_status: str
    customer_name: str | None
    customer_phone: str | None
    amount: float
    payment_status: str
    refund_status: str | None
    refund_flagged_at: str | None


class RefundList(BaseModel):
    refunds: list[RefundRow]


class OrderLine(BaseModel):
    name: str
    quantity: int
    subtotal: float


class PanelOrder(BaseModel):
    id: str
    order_number: str
    status: str
    status_label: str
    being_altered: bool
    allowed_transitions: list[str]
    customer_name: str | None
    customer_phone: str | None
    items: list[OrderLine]
    total_amount: float
    payment_method: str | None
    delivery_type: str | None
    refund_status: str | None
    opened_at: str | None


class OrderPage(BaseModel):
    orders: list[PanelOrder]
    total: int


class OrderNotification(BaseModel):
    sent: bool
    error: str | None


class OrderStatusChangeResult(BaseModel):
    order: PanelOrder
    notification: OrderNotification
