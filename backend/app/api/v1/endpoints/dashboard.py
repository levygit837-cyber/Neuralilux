from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta, timezone
import structlog

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.models import User, Instance, Contact, Conversation, Message

logger = structlog.get_logger()

router = APIRouter()


def _get_user_instance_ids(db: Session, current_user: User) -> list[str] | None:
    """Return list of instance IDs owned by user, or None for superusers (all instances)."""
    if current_user.is_superuser:
        return None
    return [
        inst.id
        for inst in db.query(Instance.id).filter(
            Instance.owner_id == current_user.id,
            Instance.is_active == True,
        ).all()
    ]


@router.get("/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard statistics"""
    try:
        user_instance_ids = _get_user_instance_ids(db, current_user)

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

        user_instance_ids = _get_user_instance_ids(db, current_user)

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
        outgoing_count = apply_instance_filter(
            db.query(Message).filter(Message.direction == "outgoing")
        ).count()
        total_count = apply_instance_filter(db.query(Message)).count()
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


@router.get("/conversations-over-time")
async def get_conversations_over_time(
    period: str = "7d",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get conversation count grouped by day for the given period (7d, 30d, 90d)."""
    try:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 7)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        user_instance_ids = _get_user_instance_ids(db, current_user)

        query = (
            db.query(
                cast(Conversation.created_at, Date).label("date"),
                func.count(Conversation.id).label("count"),
            )
            .filter(Conversation.created_at >= since)
        )
        if user_instance_ids is not None:
            query = query.filter(Conversation.instance_id.in_(user_instance_ids))

        rows = (
            query
            .group_by(cast(Conversation.created_at, Date))
            .order_by(cast(Conversation.created_at, Date))
            .all()
        )

        return {
            "data": [{"date": str(r.date), "count": r.count} for r in rows],
            "period": period,
        }
    except Exception as e:
        logger.error("Error getting conversations over time", error=str(e))
        return {"data": [], "period": period}


@router.get("/channel-metrics")
async def get_channel_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get message volume grouped by instance (top-3), mapped to channel labels."""
    try:
        user_instance_ids = _get_user_instance_ids(db, current_user)

        query = (
            db.query(Instance.name, func.count(Message.id).label("count"))
            .join(Instance, Message.instance_id == Instance.id)
        )
        if user_instance_ids is not None:
            query = query.filter(Instance.id.in_(user_instance_ids))

        rows = (
            query
            .group_by(Instance.name)
            .order_by(func.count(Message.id).desc())
            .limit(3)
            .all()
        )

        # Map top-3 instances to fixed channel display names
        channel_display_names = ["WhatsApp", "Website", "Instagram"]
        channels = [
            {"name": channel_display_names[i], "count": r.count}
            for i, r in enumerate(rows)
        ]

        return {"channels": channels}
    except Exception as e:
        logger.error("Error getting channel metrics", error=str(e))
        return {"channels": []}


@router.get("/resolution-metrics")
async def get_resolution_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get conversation distribution by resolution state."""
    try:
        user_instance_ids = _get_user_instance_ids(db, current_user)

        base = db.query(Conversation)
        if user_instance_ids is not None:
            base = base.filter(Conversation.instance_id.in_(user_instance_ids))

        # is_active=True,  is_archived=False → in progress (pending)
        # is_active=False, is_archived=False → closed/resolved
        # is_archived=True                  → archived/escalated
        resolved = base.filter(
            Conversation.is_active == False,
            Conversation.is_archived == False,
        ).count()
        pending = base.filter(
            Conversation.is_active == True,
            Conversation.is_archived == False,
        ).count()
        escalated = base.filter(Conversation.is_archived == True).count()

        return {"resolved": resolved, "pending": pending, "escalated": escalated}
    except Exception as e:
        logger.error("Error getting resolution metrics", error=str(e))
        return {"resolved": 0, "pending": 0, "escalated": 0}


@router.get("/satisfaction-metrics")
async def get_satisfaction_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get CSAT metrics: overall average score and monthly history (last 6 months)."""
    try:
        user_instance_ids = _get_user_instance_ids(db, current_user)
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)

        base = db.query(Conversation).filter(Conversation.rating.isnot(None))
        if user_instance_ids is not None:
            base = base.filter(Conversation.instance_id.in_(user_instance_ids))

        # Monthly average — PostgreSQL to_char for YYYY-MM grouping
        monthly_rows = (
            db.query(
                func.to_char(Conversation.updated_at, "YYYY-MM").label("month"),
                func.avg(Conversation.rating).label("avg_score"),
            )
            .filter(Conversation.rating.isnot(None))
            .filter(Conversation.updated_at >= six_months_ago)
            .filter(
                Conversation.instance_id.in_(user_instance_ids)
                if user_instance_ids is not None
                else True
            )
            .group_by(func.to_char(Conversation.updated_at, "YYYY-MM"))
            .order_by(func.to_char(Conversation.updated_at, "YYYY-MM"))
            .all()
        )

        current_score_raw = base.with_entities(func.avg(Conversation.rating)).scalar()
        current_score = round(float(current_score_raw), 1) if current_score_raw else 0.0

        return {
            "current_score": current_score,
            "target_score": 4.5,
            "history": [
                {"month": r.month, "score": round(float(r.avg_score), 1)}
                for r in monthly_rows
            ],
        }
    except Exception as e:
        logger.error("Error getting satisfaction metrics", error=str(e))
        return {"current_score": 0.0, "target_score": 4.5, "history": []}
