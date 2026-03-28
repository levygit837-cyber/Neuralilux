from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import structlog

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.models import User, Instance, Contact, Conversation, Message

logger = structlog.get_logger()

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard statistics"""
    try:
        # Filter by instances the user owns (unless superuser)
        if current_user.is_superuser:
            user_instance_ids = None  # All instances
        else:
            user_instance_ids = [
                inst.id for inst in db.query(Instance.id).filter(
                    Instance.owner_id == current_user.id,
                    Instance.is_active == True,
                ).all()
            ]

        # Total conversations
        conv_query = db.query(Conversation)
        if user_instance_ids is not None:
            conv_query = conv_query.filter(Conversation.instance_id.in_(user_instance_ids))
        total_conversations = conv_query.count()

        # Total messages
        msg_query = db.query(Message)
        if user_instance_ids is not None:
            msg_query = msg_query.filter(Message.instance_id.in_(user_instance_ids))
        total_messages = msg_query.count()

        # Active instances (connected status)
        instance_query = db.query(Instance).filter(Instance.status == "connected")
        if user_instance_ids is not None:
            instance_query = instance_query.filter(Instance.id.in_(user_instance_ids))
        active_instances = instance_query.count()

        # Total contacts
        contact_query = db.query(Contact)
        if user_instance_ids is not None:
            contact_query = contact_query.filter(Contact.instance_id.in_(user_instance_ids))
        total_contacts = contact_query.count()

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "active_instances": active_instances,
            "total_contacts": total_contacts,
        }
    except Exception as e:
        logger.error("Error getting dashboard stats", error=str(e))
        return {
            "total_conversations": 0,
            "total_messages": 0,
            "active_instances": 0,
            "total_contacts": 0,
        }


@router.get("/metrics")
async def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard metrics"""
    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Filter by instances the user owns (unless superuser)
        if current_user.is_superuser:
            user_instance_ids = None
        else:
            user_instance_ids = [
                inst.id for inst in db.query(Instance.id).filter(
                    Instance.owner_id == current_user.id,
                    Instance.is_active == True,
                ).all()
            ]

        def apply_instance_filter(query):
            if user_instance_ids is not None:
                return query.filter(Message.instance_id.in_(user_instance_ids))
            return query

        # Messages today
        messages_today = apply_instance_filter(
            db.query(Message).filter(Message.timestamp >= today_start)
        ).count()

        # Messages this week
        messages_this_week = apply_instance_filter(
            db.query(Message).filter(Message.timestamp >= week_start)
        ).count()

        # Response rate (outgoing messages / total messages) * 100
        outgoing_query = apply_instance_filter(
            db.query(Message).filter(Message.direction == "outgoing")
        )
        outgoing_count = outgoing_query.count()
        
        total_query = apply_instance_filter(db.query(Message))
        total_count = total_query.count()
        
        response_rate = (outgoing_count / total_count * 100) if total_count > 0 else 0

        return {
            "messages_today": messages_today,
            "messages_this_week": messages_this_week,
            "response_rate": round(response_rate, 1),
            "avg_response_time": None,  # Future implementation
        }
    except Exception as e:
        logger.error("Error getting dashboard metrics", error=str(e))
        return {
            "messages_today": 0,
            "messages_this_week": 0,
            "response_rate": 0,
            "avg_response_time": None,
        }
