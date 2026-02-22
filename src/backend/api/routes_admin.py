from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.auth.rbac import role_required
from src.backend.db.crud import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    list_all_users,
    update_user,
)
from src.backend.db.database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_ROLES = {"admin", "reviewer", "enterprise_user"}


class CreateUserRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = "enterprise_user"


class UpdateUserRequest(BaseModel):
    name: str | None = None
    role: str | None = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/users", response_model=list[UserResponse])
def admin_list_users(
    current_user: dict = Depends(role_required(["admin"])),
    db: Session = Depends(get_db),
):
    users = list_all_users(db)
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            name=u.name,
            role=u.role,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def admin_create_user(
    req: CreateUserRequest,
    current_user: dict = Depends(role_required(["admin"])),
    db: Session = Depends(get_db),
):
    if req.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}",
        )
    existing = get_user_by_email(db, req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = create_user(db, email=req.email, password=req.password, name=req.name, role=req.role)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
def admin_update_user(
    user_id: str,
    req: UpdateUserRequest,
    current_user: dict = Depends(role_required(["admin"])),
    db: Session = Depends(get_db),
):
    if req.role is not None and req.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}",
        )
    user = update_user(db, user_id, name=req.name, role=req.role)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/users/{user_id}/deactivate", response_model=UserResponse)
def admin_deactivate_user(
    user_id: str,
    current_user: dict = Depends(role_required(["admin"])),
    db: Session = Depends(get_db),
):
    user = update_user(db, user_id, is_active=False)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
    )


@router.post("/users/{user_id}/activate", response_model=UserResponse)
def admin_activate_user(
    user_id: str,
    current_user: dict = Depends(role_required(["admin"])),
    db: Session = Depends(get_db),
):
    user = update_user(db, user_id, is_active=True)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
    )
