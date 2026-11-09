from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.identity import User
from app.schemas.activities import (
    ActivityConfigurationResponse,
    ActivityConfigurationUpdate,
    PuzzleCreateRequest,
    PuzzleResponse,
    SpinRewardOptionResponse,
)
from app.schemas.dashboard import AdminDashboardResponse
from app.services import activity_service
from app.services import dashboard_service
from app.services.activity_service import ActivityError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/health")
def admin_health(_: User = Depends(require_roles("admin"))):
    return {"status": "ok"}


@router.get("/dashboard", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> AdminDashboardResponse:
    return AdminDashboardResponse.model_validate(dashboard_service.get_admin_dashboard(db))


@router.get("/activities/configuration", response_model=ActivityConfigurationResponse)
def get_activity_configuration(
    _: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ActivityConfigurationResponse:
    try:
        configuration = activity_service.get_activity_configuration(db)
    except ActivityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return ActivityConfigurationResponse(
        enabled=configuration.enabled,
        puzzle_enabled=configuration.puzzle_enabled,
        daily_activity_cap=configuration.daily_activity_cap,
        rewards=[
            SpinRewardOptionResponse(
                points=reward.points,
                probability_basis_points=reward.probability_basis_points,
            )
            for reward in configuration.rewards
        ],
        updated_at=configuration.updated_at,
    )


@router.put("/activities/configuration", response_model=ActivityConfigurationResponse)
def update_activity_configuration(
    payload: ActivityConfigurationUpdate,
    actor: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> ActivityConfigurationResponse:
    try:
        configuration = activity_service.update_activity_configuration(db, actor.id, payload)
    except ActivityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return ActivityConfigurationResponse(
        enabled=configuration.enabled,
        puzzle_enabled=configuration.puzzle_enabled,
        daily_activity_cap=configuration.daily_activity_cap,
        rewards=[
            SpinRewardOptionResponse(
                points=reward.points,
                probability_basis_points=reward.probability_basis_points,
            )
            for reward in configuration.rewards
        ],
        updated_at=configuration.updated_at,
    )


@router.post("/puzzles", response_model=PuzzleResponse, status_code=status.HTTP_201_CREATED)
def create_puzzle(
    payload: PuzzleCreateRequest,
    actor: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> PuzzleResponse:
    try:
        question = activity_service.create_puzzle(db, actor.id, payload)
    except ActivityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return PuzzleResponse(
        id=question.id,
        prompt=question.prompt,
        reward_points=question.reward_points,
        business_date=question.business_date,
        attempted=False,
        is_active=question.is_active,
    )
