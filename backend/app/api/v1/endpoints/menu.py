from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.database import get_db
from app.schemas.menu import (
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    MenuManagementResponse,
)
from app.services.menu_management_service import (
    create_menu_category,
    create_menu_item,
    delete_menu_category,
    delete_menu_item,
    get_menu_management_snapshot,
    update_menu_category,
    update_menu_item,
)


router = APIRouter()


@router.get("", response_model=MenuManagementResponse)
async def read_active_menu(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_menu_management_snapshot(db, current_user.company_id)


@router.post("/categories", response_model=MenuCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: MenuCategoryCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return create_menu_category(db, current_user.company_id, payload)


@router.patch("/categories/{category_id}", response_model=MenuCategoryResponse)
async def update_category(
    category_id: str,
    payload: MenuCategoryUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return update_menu_category(db, current_user.company_id, category_id, payload)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    delete_menu_category(db, current_user.company_id, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return create_menu_item(db, current_user.company_id, payload)


@router.patch("/items/{item_id}", response_model=MenuItemResponse)
async def update_item(
    item_id: str,
    payload: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return update_menu_item(db, current_user.company_id, item_id, payload)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    delete_menu_item(db, current_user.company_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
