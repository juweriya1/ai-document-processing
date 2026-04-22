from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from src.backend.auth.jwt_handler import create_access_token
from src.backend.db.crud import create_user, get_user_by_email, verify_password
from src.backend.db.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: str = "enterprise_user"


# class LoginRequest(BaseModel):
#     email: str
#     password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str


# class LoginResponse(BaseModel):
#     accessToken: str
#     tokenType: str = "bearer"
#     user: UserResponse

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = get_user_by_email(db, req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = create_user(db, email=req.email, password=req.password, name=req.name, role=req.role)
    return UserResponse(id=user.id, email=user.email, name=user.name, role=user.role)


@router.post("/login", response_model=LoginResponse)
def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    user = get_user_by_email(db, form_data.username)

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(
        data={"sub": user.email, "role": user.role, "user_id": user.id}
    )

    # return LoginResponse(
    #     accessToken=token,
    #     user=UserResponse(
    #         id=user.id,
    #         email=user.email,
    #         name=user.name,
    #         role=user.role,
    #     ),
    # )

    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
        ),
    )
