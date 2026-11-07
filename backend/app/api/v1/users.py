from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.identity import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        phone=user.phone,
        full_name=user.full_name,
        role=user.role.name,
    )
