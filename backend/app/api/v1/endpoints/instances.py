from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db

router = APIRouter()


@router.get("/")
async def list_instances(db: Session = Depends(get_db)):
    """List all WhatsApp instances"""
    return {"message": "List instances endpoint - to be implemented"}


@router.post("/")
async def create_instance(db: Session = Depends(get_db)):
    """Create a new WhatsApp instance"""
    return {"message": "Create instance endpoint - to be implemented"}


@router.get("/{instance_id}")
async def get_instance(instance_id: str, db: Session = Depends(get_db)):
    """Get instance details"""
    return {"message": f"Get instance {instance_id} - to be implemented"}


@router.put("/{instance_id}")
async def update_instance(instance_id: str, db: Session = Depends(get_db)):
    """Update instance configuration"""
    return {"message": f"Update instance {instance_id} - to be implemented"}


@router.delete("/{instance_id}")
async def delete_instance(instance_id: str, db: Session = Depends(get_db)):
    """Delete an instance"""
    return {"message": f"Delete instance {instance_id} - to be implemented"}


@router.get("/{instance_id}/qrcode")
async def get_qrcode(instance_id: str, db: Session = Depends(get_db)):
    """Get QR code for instance connection"""
    return {"message": f"Get QR code for {instance_id} - to be implemented"}


@router.post("/{instance_id}/connect")
async def connect_instance(instance_id: str, db: Session = Depends(get_db)):
    """Connect instance to WhatsApp"""
    return {"message": f"Connect instance {instance_id} - to be implemented"}


@router.post("/{instance_id}/disconnect")
async def disconnect_instance(instance_id: str, db: Session = Depends(get_db)):
    """Disconnect instance from WhatsApp"""
    return {"message": f"Disconnect instance {instance_id} - to be implemented"}
