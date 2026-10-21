from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User, Instance


def _get_instance_for_user(
    db: Session,
    instance_id: str,
    current_user: User,
) -> Instance:
    """Helper to fetch and validate instance ownership."""
    instance = db.query(Instance).filter(
        Instance.id == instance_id,
        Instance.is_active == True,
    ).first()

    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Instance not found",
        )

    if not current_user.is_superuser and instance.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this instance",
        )

    return instance
