import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.activities import (
    AdminAuditLog,
    DailyActivityLimit,
    PuzzleAttempt,
    PuzzleQuestion,
    SpinConfiguration,
    SpinRewardOption,
    SpinSession,
)
from app.models.wallet import Wallet, WalletTransaction, WalletTransactionType
from app.schemas.activities import ActivityConfigurationUpdate, PuzzleAnswerRequest, PuzzleCreateRequest


class ActivityError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ActivityStatus:
    enabled: bool
    spun_today: bool
    spins_used: int
    spin_limit: int
    spins_remaining: int
    daily_points_earned: int
    daily_points_remaining: int
    rewards: list[tuple[int, int]]


@dataclass(frozen=True)
class SpinResult:
    spun_today: bool
    spins_used: int
    spin_limit: int
    spins_remaining: int
    points_awarded: int
    reward_points: int
    reward_index: int
    business_date: date
    daily_points_earned: int
    daily_points_remaining: int


@dataclass(frozen=True)
class PuzzleResult:
    is_correct: bool
    points_awarded: int
    daily_points_earned: int
    daily_points_remaining: int


def current_business_date(now: datetime | None = None) -> date:
    event_time = now or datetime.now(timezone.utc)
    if event_time.tzinfo is None:
        raise ActivityError(422, "Activity time must include a timezone")
    return event_time.astimezone(ZoneInfo(settings.business_timezone)).date()


def _configuration(db: Session, *, lock: bool = False) -> SpinConfiguration:
    statement = (
        select(SpinConfiguration)
        .options(selectinload(SpinConfiguration.rewards))
        .where(SpinConfiguration.id == 1)
    )
    if lock:
        statement = statement.with_for_update()
    configuration = db.execute(statement).unique().scalar_one_or_none()
    if configuration is None:
        raise ActivityError(503, "Activity configuration is missing; run database migrations")
    return configuration


def _wallet(db: Session, user_id: UUID) -> Wallet:
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
    if wallet is None:
        raise ActivityError(404, "Wallet not found")
    ledger_balance = db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.points_delta), 0)).where(
            WalletTransaction.wallet_id == wallet.id
        )
    )
    if wallet.balance_points != ledger_balance:
        raise ActivityError(409, "Wallet balance does not match its transaction ledger")
    return wallet


def _daily_limit(db: Session, user_id: UUID, business_day: date) -> DailyActivityLimit:
    limit = db.get(DailyActivityLimit, (user_id, business_day), with_for_update=True)
    if limit is None:
        limit = DailyActivityLimit(user_id=user_id, business_date=business_day, points_earned=0)
        db.add(limit)
        db.flush()
    return limit


def _remaining(configuration: SpinConfiguration, daily_limit: DailyActivityLimit) -> int:
    return max(0, configuration.daily_activity_cap - daily_limit.points_earned)


def _spin_limit() -> int:
    if settings.environment.lower() == "development":
        return settings.development_spin_limit
    return 1


def get_spin_status(db: Session, user_id: UUID, *, now: datetime | None = None) -> ActivityStatus:
    business_day = current_business_date(now)
    configuration = _configuration(db)
    limit = db.get(DailyActivityLimit, (user_id, business_day))
    earned = limit.points_earned if limit is not None else 0
    spins_used = db.scalar(
        select(func.count()).select_from(SpinSession).where(
            SpinSession.user_id == user_id,
            SpinSession.business_date == business_day,
        )
    ) or 0
    spin_limit = _spin_limit()
    spins_remaining = max(0, spin_limit - spins_used)
    return ActivityStatus(
        enabled=configuration.enabled,
        spun_today=spins_remaining == 0,
        spins_used=spins_used,
        spin_limit=spin_limit,
        spins_remaining=spins_remaining,
        daily_points_earned=earned,
        daily_points_remaining=max(0, configuration.daily_activity_cap - earned),
        rewards=[
            (reward.points, reward.probability_basis_points)
            for reward in sorted(configuration.rewards, key=lambda item: item.points)
        ],
    )


def spin(db: Session, user_id: UUID, *, now: datetime | None = None) -> SpinResult:
    business_day = current_business_date(now)
    try:
        wallet = _wallet(db, user_id)
        configuration = _configuration(db, lock=True)
        if not configuration.enabled:
            raise ActivityError(409, "Daily spin is currently disabled")
        spins_used = db.scalar(
            select(func.count()).select_from(SpinSession).where(
                SpinSession.user_id == user_id,
                SpinSession.business_date == business_day,
            )
        ) or 0
        spin_limit = _spin_limit()
        if spins_used >= spin_limit:
            raise ActivityError(409, "You have already used all of today's spins")
        if not configuration.rewards:
            raise ActivityError(503, "No spin rewards are configured")

        daily_limit = _daily_limit(db, user_id, business_day)
        remaining = _remaining(configuration, daily_limit)
        rewards = sorted(configuration.rewards, key=lambda item: item.points)
        total = sum(reward.probability_basis_points for reward in rewards)
        if total != 10_000:
            raise ActivityError(503, "Spin reward probabilities are not configured correctly")
        ticket = secrets.randbelow(10_000)
        cumulative = 0
        selected: SpinRewardOption | None = None
        selected_index = -1
        for index, reward in enumerate(rewards):
            cumulative += reward.probability_basis_points
            if ticket < cumulative:
                selected = reward
                selected_index = index
                break
        if selected is None:
            raise ActivityError(503, "Spin reward probabilities are not configured correctly")

        awarded = min(selected.points, remaining)
        db.add(
            SpinSession(
                user_id=user_id,
                business_date=business_day,
                reward_points=awarded,
                probability_basis_points=selected.probability_basis_points,
            )
        )
        _credit_activity(db, wallet, user_id, awarded, WalletTransactionType.SPIN_REWARD, "Daily spin reward")
        daily_limit.points_earned += awarded
        db.commit()
        spins_used += 1
        spins_remaining = max(0, spin_limit - spins_used)
        return SpinResult(
            spun_today=spins_remaining == 0,
            spins_used=spins_used,
            spin_limit=spin_limit,
            spins_remaining=spins_remaining,
            points_awarded=awarded,
            reward_points=selected.points,
            reward_index=selected_index,
            business_date=business_day,
            daily_points_earned=daily_limit.points_earned,
            daily_points_remaining=_remaining(configuration, daily_limit),
        )
    except IntegrityError as exc:
        db.rollback()
        raise ActivityError(409, "Spin could not be recorded; please refresh and try again") from exc
    except ActivityError:
        db.rollback()
        raise


def get_today_puzzle(
    db: Session, user_id: UUID, *, now: datetime | None = None
) -> tuple[PuzzleQuestion, bool] | None:
    business_day = current_business_date(now)
    configuration = _configuration(db)
    if not configuration.puzzle_enabled:
        return None
    question = db.scalar(
        select(PuzzleQuestion).where(
            PuzzleQuestion.business_date == business_day,
            PuzzleQuestion.is_active.is_(True),
        )
    )
    if question is None:
        return None
    attempted = db.scalar(
        select(PuzzleAttempt.id).where(
            PuzzleAttempt.question_id == question.id,
            PuzzleAttempt.user_id == user_id,
        )
    ) is not None
    return question, attempted


def submit_puzzle_answer(
    db: Session,
    user_id: UUID,
    question_id: UUID,
    payload: PuzzleAnswerRequest | str,
    *,
    now: datetime | None = None,
) -> PuzzleResult:
    answer = payload if isinstance(payload, str) else payload.answer
    business_day = current_business_date(now)
    try:
        wallet = _wallet(db, user_id)
        configuration = _configuration(db, lock=True)
        if not configuration.puzzle_enabled:
            raise ActivityError(409, "Puzzle activities are currently disabled")
        question = db.scalar(
            select(PuzzleQuestion)
            .where(
                PuzzleQuestion.id == question_id,
                PuzzleQuestion.business_date == business_day,
                PuzzleQuestion.is_active.is_(True),
            )
            .with_for_update()
        )
        if question is None:
            raise ActivityError(404, "Today's puzzle was not found")
        if db.scalar(
            select(PuzzleAttempt.id).where(
                PuzzleAttempt.question_id == question_id,
                PuzzleAttempt.user_id == user_id,
            )
        ) is not None:
            raise ActivityError(409, "You have already submitted an answer for this puzzle")

        daily_limit = _daily_limit(db, user_id, business_day)
        correct = hmac.compare_digest(_answer_digest(answer), question.answer_hash)
        awarded = min(question.reward_points, _remaining(configuration, daily_limit)) if correct else 0
        db.add(
            PuzzleAttempt(
                question_id=question.id,
                user_id=user_id,
                is_correct=correct,
                points_awarded=awarded,
            )
        )
        _credit_activity(
            db,
            wallet,
            user_id,
            awarded,
            WalletTransactionType.PUZZLE_REWARD,
            "Puzzle reward",
            f"{question.id}:{user_id}",
        )
        daily_limit.points_earned += awarded
        db.commit()
        return PuzzleResult(correct, awarded, daily_limit.points_earned, _remaining(configuration, daily_limit))
    except IntegrityError as exc:
        db.rollback()
        raise ActivityError(409, "You have already submitted an answer for this puzzle") from exc
    except ActivityError:
        db.rollback()
        raise


def _credit_activity(
    db: Session,
    wallet: Wallet,
    user_id: UUID,
    points: int,
    transaction_type: WalletTransactionType,
    description: str,
    reference_id: UUID | str | None = None,
) -> None:
    if points == 0:
        return
    wallet.balance_points += points
    db.add(
        WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            transaction_type=transaction_type.value,
            points_delta=points,
            description=description,
            reference_id=str(reference_id or uuid4()),
        )
    )


def get_activity_configuration(db: Session) -> SpinConfiguration:
    return _configuration(db)


def update_activity_configuration(
    db: Session,
    actor_id: UUID,
    payload: ActivityConfigurationUpdate,
) -> SpinConfiguration:
    configuration = _configuration(db, lock=True)
    before = {
        "enabled": configuration.enabled,
        "puzzle_enabled": configuration.puzzle_enabled,
        "daily_activity_cap": configuration.daily_activity_cap,
        "rewards": [
            {"points": item.points, "probability_basis_points": item.probability_basis_points}
            for item in configuration.rewards
        ],
    }
    configuration.enabled = payload.enabled
    configuration.puzzle_enabled = payload.puzzle_enabled
    configuration.daily_activity_cap = payload.daily_activity_cap
    configuration.updated_by = actor_id
    configuration.rewards.clear()
    db.flush()
    configuration.rewards.extend(
        SpinRewardOption(
            points=item.points,
            probability_basis_points=item.probability_basis_points,
        )
        for item in payload.rewards
    )
    db.flush()
    after = payload.model_dump()
    db.add(
        AdminAuditLog(
            actor_user_id=actor_id,
            action="update",
            entity_type="activity_configuration",
            entity_id="1",
            before_data=before,
            after_data=after,
        )
    )
    db.commit()
    return _configuration(db)


def create_puzzle(db: Session, actor_id: UUID, payload: PuzzleCreateRequest) -> PuzzleQuestion:
    question = PuzzleQuestion(
        business_date=payload.business_date,
        prompt=payload.prompt.strip(),
        answer_hash=_answer_digest(payload.answer),
        reward_points=payload.reward_points,
        is_active=payload.is_active,
        created_by=actor_id,
    )
    db.add(question)
    try:
        db.flush()
        db.add(
            AdminAuditLog(
                actor_user_id=actor_id,
                action="create",
                entity_type="puzzle_question",
                entity_id=str(question.id),
                before_data=None,
                after_data={
                    "business_date": payload.business_date.isoformat(),
                    "prompt": payload.prompt.strip(),
                    "reward_points": payload.reward_points,
                    "is_active": payload.is_active,
                },
            )
        )
        db.commit()
        db.refresh(question)
    except IntegrityError as exc:
        db.rollback()
        raise ActivityError(409, "A puzzle already exists for that business date") from exc
    return question


def _answer_digest(answer: str) -> str:
    key = settings.jwt_secret_key.get_secret_value().encode("utf-8")
    normalized = answer.strip().casefold().encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()
