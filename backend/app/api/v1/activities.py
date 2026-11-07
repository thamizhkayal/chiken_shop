from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.identity import User
from app.schemas.activities import (
    PuzzleAttemptResponse,
    PuzzleResponse,
    PuzzleAnswerRequest,
    SpinRewardOptionResponse,
    SpinRewardResponse,
    SpinStatusResponse,
)
from app.services import activity_service
from app.services.activity_service import ActivityError

router = APIRouter(tags=["activities"])


@router.get("/spin/status", response_model=SpinStatusResponse)
def get_spin_status(
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> SpinStatusResponse:
    try:
        result = activity_service.get_spin_status(db, user.id)
    except ActivityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SpinStatusResponse(
        enabled=result.enabled,
        spun_today=result.spun_today,
        daily_points_earned=result.daily_points_earned,
        daily_points_remaining=result.daily_points_remaining,
        rewards=[
            SpinRewardOptionResponse(points=points, probability_basis_points=probability)
            for points, probability in result.rewards
        ],
    )


@router.post("/spin", response_model=SpinRewardResponse)
@limiter.limit("3/minute")
def spin(
    request: Request,
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> SpinRewardResponse:
    del request
    try:
        result = activity_service.spin(db, user.id)
    except ActivityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SpinRewardResponse(
        spun_today=result.spun_today,
        points_awarded=result.points_awarded,
        reward_points=result.reward_points,
        reward_index=result.reward_index,
        business_date=result.business_date,
        daily_points_earned=result.daily_points_earned,
        daily_points_remaining=result.daily_points_remaining,
    )


@router.get("/puzzles/today", response_model=PuzzleResponse | None)
def get_today_puzzle(
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> PuzzleResponse | None:
    try:
        result = activity_service.get_today_puzzle(db, user.id)
    except ActivityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if result is None:
        return None
    question, attempted = result
    return PuzzleResponse(
        id=question.id,
        prompt=question.prompt,
        reward_points=question.reward_points,
        business_date=question.business_date,
        attempted=attempted,
        is_active=question.is_active,
    )


@router.post("/puzzles/{question_id}/attempt", response_model=PuzzleAttemptResponse)
@limiter.limit("5/minute")
def submit_puzzle_answer(
    request: Request,
    question_id: UUID,
    payload: PuzzleAnswerRequest,
    user: User = Depends(require_roles("customer")),
    db: Session = Depends(get_db),
) -> PuzzleAttemptResponse:
    del request
    try:
        result = activity_service.submit_puzzle_answer(db, user.id, question_id, payload)
    except ActivityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return PuzzleAttemptResponse(
        is_correct=result.is_correct,
        points_awarded=result.points_awarded,
        daily_points_earned=result.daily_points_earned,
        daily_points_remaining=result.daily_points_remaining,
    )
