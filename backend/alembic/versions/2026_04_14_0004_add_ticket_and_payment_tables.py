"""Add Ticket and PaymentRecord tables

Revision ID: 2026_04_14_0004
Revises: 2026_04_14_0003
Create Date: 2026-04-14 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '2026_04_14_0004'
down_revision = 'h3i4j5k6l8m9'
branch_labels = None
depends_on = None


def upgrade():
    # Add pix_key column to companies table if not exists
    op.execute("""
        ALTER TABLE companies 
        ADD COLUMN IF NOT EXISTS pix_key VARCHAR(500)
    """)

    # Create tickets table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id VARCHAR NOT NULL,
            conversation_id VARCHAR NOT NULL,
            instance_id VARCHAR NOT NULL,
            contact_id VARCHAR NOT NULL,
            agent_type VARCHAR(20) NOT NULL,
            reason TEXT NOT NULL,
            content TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            assigned_to VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id),
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (instance_id) REFERENCES instances(id)
        )
    """)

    # Create indexes for tickets
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tickets_assigned_to ON tickets(assigned_to)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tickets_contact_id ON tickets(contact_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tickets_conversation_id ON tickets(conversation_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_tickets_instance_id ON tickets(instance_id)
    """)

    # Create payment_records table if not exists
    op.execute("""
        CREATE TABLE IF NOT EXISTS payment_records (
            id VARCHAR NOT NULL,
            order_id VARCHAR NOT NULL,
            conversation_id VARCHAR NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            pix_key VARCHAR(255) NOT NULL,
            qr_code_data TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            payment_method VARCHAR(20) NOT NULL DEFAULT 'pix',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            paid_at TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        )
    """)

    # Create indexes for payment_records
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payment_records_conversation_id ON payment_records(conversation_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_payment_records_order_id ON payment_records(order_id)
    """)

    # Update customer_orders status type if exists
    try:
        op.execute("""
            ALTER TABLE customer_orders 
            ALTER COLUMN status TYPE VARCHAR(30)
        """)
    except Exception:
        pass  # Table may not exist or column already correct type


def downgrade():
    # Drop payment_records table
    op.drop_index(op.f('ix_payment_records_order_id'), table_name='payment_records')
    op.drop_index(op.f('ix_payment_records_conversation_id'), table_name='payment_records')
    op.drop_table('payment_records')

    # Drop tickets table
    op.drop_index(op.f('ix_tickets_instance_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_conversation_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_contact_id'), table_name='tickets')
    op.drop_index(op.f('ix_tickets_assigned_to'), table_name='tickets')
    op.drop_table('tickets')

    # Remove pix_key column from companies table
    op.drop_column('companies', 'pix_key')
