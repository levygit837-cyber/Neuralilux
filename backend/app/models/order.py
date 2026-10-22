from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, Index, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.base import generate_uuid


class CustomerOrder(Base):
    __tablename__ = "customer_orders"

    id = Column(String, primary_key=True, default=generate_uuid)
    order_number = Column(String(50), unique=True, nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    instance_id = Column(String, ForeignKey("instances.id"), nullable=False, index=True)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=False, index=True)
    remote_jid = Column(String, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="open")  # open, collecting_data, ready_for_confirmation, closed, cancelled, in_production, sent, delivered, abandoned (Session acabou com o Order ativo)
    customer_name = Column(String(200))
    customer_address = Column(Text)
    customer_phone = Column(String(30))
    payment_method = Column(String(100))
    delivery_type = Column(String(20))  # "entrega" | "retirada"
    delivery_fee = Column(Numeric(10, 2), nullable=False, default=0, server_default="0")  # taxa da zona, já somada em total_amount
    change_for = Column(Numeric(10, 2))  # troco_para (pagamento em dinheiro)
    total_amount = Column(Numeric(10, 2), nullable=False, default=0)
    opened_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at = Column(DateTime(timezone=True))
    recap_signature = Column(String(64))  # impressão do Order na última recapitulação; mudou, recapitular de novo
    recap_turn_id = Column(String(32))  # Turn em que o Contact viu essa recapitulação; `finalizar` exige um Turn posterior
    export_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    conversation = relationship("Conversation", back_populates="orders")
    instance = relationship("Instance", back_populates="orders")
    contact = relationship("Contact", back_populates="orders")
    items = relationship(
        "CustomerOrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="CustomerOrderItem.sort_order.asc()",
    )


class CustomerOrderItem(Base):
    __tablename__ = "customer_order_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    order_id = Column(String, ForeignKey("customer_orders.id"), nullable=False, index=True)
    menu_item_id = Column(String, ForeignKey("menu_items.id"), nullable=True, index=True)
    item_name = Column(String(200), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False, default=0)
    subtotal_price = Column(Numeric(10, 2), nullable=False, default=0)
    notes = Column(Text)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order = relationship("CustomerOrder", back_populates="items")


class DeliveryZone(Base):
    """Zonas de entrega com taxas baseadas em bairro/região."""
    __tablename__ = "delivery_zones"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=True, index=True)  # NULL: zona legada, ignorada pelo Pack
    name = Column(String(200), nullable=False)  # Nome da zona (ex: "Centro", "Zona Norte")
    neighborhoods = Column(JSONB, nullable=False)  # Lista de bairros nesta zona
    delivery_fee = Column(Numeric(10, 2), nullable=False)  # Taxa de entrega
    minimum_order_value = Column(Numeric(10, 2), default=0)  # Valor mínimo pedido (opcional)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PaymentRecord(Base):
    """Registros de pagamentos para vendas fechadas."""
    __tablename__ = "payment_records"

    id = Column(String, primary_key=True, default=generate_uuid)
    order_id = Column(String, ForeignKey("customer_orders.id"), nullable=False, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)  # Valor do pagamento
    pix_key = Column(String(255), nullable=False)  # Chave Pix configurada
    qr_code_data = Column(Text, nullable=True)  # Dados do QR Code gerado
    status = Column(String(20), nullable=False, default="pending")  # "pending", "paid", "cancelled", "expired"
    payment_method = Column(String(20), nullable=False, default="pix")  # "pix"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # Um Pix por Order: o dedup de `catalog_orders.pix.ensure_payment_record` se apoia neste índice.
    __table_args__ = (
        Index(
            "uq_payment_records_order_pix",
            "order_id",
            unique=True,
            postgresql_where=text("payment_method = 'pix'"),
            sqlite_where=text("payment_method = 'pix'"),
        ),
    )

    # Relationships
    order = relationship("CustomerOrder", foreign_keys=[order_id])
    conversation = relationship("Conversation", foreign_keys=[conversation_id])
