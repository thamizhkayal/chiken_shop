from fastapi import APIRouter, Depends

from app.api.deps import require_roles
from app.models.identity import User

router = APIRouter(prefix="/staff", tags=["staff"])


@router.get("/health")
def staff_health(_: User = Depends(require_roles("staff", "admin"))):
    return {"status": "ok"}
