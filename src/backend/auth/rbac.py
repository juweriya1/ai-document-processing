from fastapi import Depends, HTTPException, status

from src.backend.auth.jwt_handler import get_current_user


def require_role(allowed_roles: list[str]):
    def checker(user):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user
    return checker


def role_required(allowed_roles: list[str]):
    def dependency(current_user: dict = Depends(get_current_user)):
        role = current_user.get("role")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    return dependency
