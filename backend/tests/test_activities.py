from datetime import datetime, timezone

import pytest

from app.models.activities import AdminAuditLog, PuzzleQuestion, SpinConfiguration, SpinRewardOption
from app.models.identity import Role, User
from app.models.wallet import Wallet, WalletTransaction, WalletTransactionType
from app.core.security import hash_password
from app.schemas.activities import ActivityConfigurationUpdate, PuzzleAnswerRequest
from app.services.activity_service import (
    ActivityError,
    _answer_digest,
    current_business_date,
    get_spin_status,
    spin,
    submit_puzzle_answer,
    update_activity_configuration,
)


def create_customer(db_session, email: str = "activities@example.com"):
    role = db_session.query(Role).filter_by(name="customer").one()
    user = User(role_id=role.id, email=email, full_name="Activity Customer", password_hash="unused")
    db_session.add(user)
    db_session.flush()
    db_session.add(Wallet(user_id=user.id))
    db_session.commit()
    return user


def create_configuration(db_session, *, cap: int = 20):
    configuration = SpinConfiguration(id=1, enabled=True, puzzle_enabled=True, daily_activity_cap=cap)
    configuration.rewards = [
        SpinRewardOption(points=5, probability_basis_points=10_000),
    ]
    db_session.add(configuration)
    db_session.commit()
    return configuration


def test_spin_is_server_awarded_once_and_writes_ledger(db_session, monkeypatch):
    user = create_customer(db_session)
    configuration = create_configuration(db_session)
    for existing_reward in configuration.rewards:
        db_session.delete(existing_reward)
    db_session.flush()
    configuration.rewards = [
        SpinRewardOption(points=1, probability_basis_points=5_000),
        SpinRewardOption(points=5, probability_basis_points=5_000),
    ]
    db_session.commit()
    monkeypatch.setattr("app.services.activity_service.secrets.randbelow", lambda _: 9_999)
    now = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

    outcome = spin(db_session, user.id, now=now)

    assert outcome.points_awarded == 5
    assert outcome.daily_points_earned == 5
    transaction = db_session.query(WalletTransaction).filter_by(
        transaction_type=WalletTransactionType.SPIN_REWARD.value
    ).one()
    assert transaction.points_delta == 5
    assert db_session.query(Wallet).filter_by(user_id=user.id).one().balance_points == 5
    with pytest.raises(ActivityError, match="already used"):
        spin(db_session, user.id, now=now)


def test_daily_cap_is_shared_by_spin_and_puzzle(db_session):
    user = create_customer(db_session)
    create_configuration(db_session, cap=6)
    now = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
    question = PuzzleQuestion(
        business_date=now.date(),
        prompt="What is 2 + 2?",
        answer_hash=_answer_digest("4"),
        reward_points=5,
        is_active=True,
    )
    db_session.add(question)
    db_session.commit()

    spin_result = spin(db_session, user.id, now=now)
    puzzle_result = submit_puzzle_answer(
        db_session, user.id, question.id, PuzzleAnswerRequest(answer="4"), now=now
    )

    assert spin_result.points_awarded == 5
    assert puzzle_result.points_awarded == 1
    assert puzzle_result.daily_points_earned == 6
    status = get_spin_status(db_session, user.id, now=now)
    assert status.daily_points_remaining == 0
    assert db_session.query(Wallet).filter_by(user_id=user.id).one().balance_points == 6


def test_puzzle_wrong_answer_is_recorded_and_cannot_be_replayed(db_session):
    user = create_customer(db_session)
    create_configuration(db_session)
    now = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
    question = PuzzleQuestion(
        business_date=now.date(),
        prompt="What is 2 + 2?",
        answer_hash=_answer_digest("4"),
        reward_points=3,
        is_active=True,
    )
    db_session.add(question)
    db_session.commit()

    result = submit_puzzle_answer(
        db_session, user.id, question.id, PuzzleAnswerRequest(answer="wrong"), now=now
    )

    assert not result.is_correct
    assert result.points_awarded == 0
    assert db_session.query(WalletTransaction).count() == 0
    with pytest.raises(ActivityError, match="already submitted"):
        submit_puzzle_answer(
            db_session, user.id, question.id, PuzzleAnswerRequest(answer="4"), now=now
        )


def test_admin_reward_update_is_audited_and_probabilities_must_total_10000(db_session):
    admin_role = db_session.query(Role).filter_by(name="admin").one()
    admin = User(role_id=admin_role.id, email="admin-activities@example.com", full_name="Admin", password_hash="unused")
    db_session.add(admin)
    db_session.flush()
    create_configuration(db_session)
    payload = ActivityConfigurationUpdate(
        enabled=True,
        puzzle_enabled=False,
        daily_activity_cap=20,
        rewards=[{"points": 2, "probability_basis_points": 10_000}],
    )

    updated = update_activity_configuration(db_session, admin.id, payload)

    assert updated.rewards[0].points == 2
    assert updated.puzzle_enabled is False
    assert db_session.query(AdminAuditLog).count() == 1
    with pytest.raises(ValueError, match="total 10000"):
        ActivityConfigurationUpdate(
            enabled=True,
            puzzle_enabled=True,
            daily_activity_cap=20,
            rewards=[{"points": 1, "probability_basis_points": 9_999}],
        )


def test_customer_activity_endpoints_return_only_server_results(client, test_session_factory):
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "activity-http@example.com",
            "full_name": "Activity HTTP",
            "password": "a-very-long-password",
        },
    )
    assert registration.status_code == 201
    with test_session_factory() as session:
        user = session.query(User).filter_by(email="activity-http@example.com").one()
        create_configuration(session)
        question = PuzzleQuestion(
            business_date=current_business_date(),
            prompt="What is 2 + 2?",
            answer_hash=_answer_digest("4"),
            reward_points=3,
            is_active=True,
        )
        session.add(question)
        session.commit()
        question_id = question.id

    status_response = client.get("/api/v1/spin/status")
    assert status_response.status_code == 200
    assert status_response.json()["rewards"] == [{"points": 5, "probability_basis_points": 10000}]

    spin_response = client.post("/api/v1/spin")
    assert spin_response.status_code == 200
    assert spin_response.json()["points_awarded"] == 5
    assert spin_response.json()["reward_points"] == 5
    assert spin_response.json()["reward_index"] == 0

    puzzle_response = client.get("/api/v1/puzzles/today")
    assert puzzle_response.status_code == 200
    assert puzzle_response.json()["id"] == str(question_id)
    assert "answer_hash" not in puzzle_response.json()
    answer_response = client.post(
        f"/api/v1/puzzles/{question_id}/attempt",
        json={"answer": "4"},
    )
    assert answer_response.status_code == 200
    assert answer_response.json()["points_awarded"] == 3


def test_admin_activity_routes_audit_changes_and_allow_privileged_login_without_wallet(
    client, test_session_factory
):
    with test_session_factory() as session:
        admin_role = session.query(Role).filter_by(name="admin").one()
        admin = User(
            role_id=admin_role.id,
            email="activity-admin@example.com",
            full_name="Activity Admin",
            password_hash=hash_password("a-very-long-password"),
        )
        session.add(admin)
        create_configuration(session)

    login_response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "activity-admin@example.com", "password": "a-very-long-password"},
    )
    assert login_response.status_code == 200

    configuration_response = client.get("/api/v1/admin/activities/configuration")
    assert configuration_response.status_code == 200
    update_response = client.put(
        "/api/v1/admin/activities/configuration",
        json={
            "enabled": True,
            "puzzle_enabled": False,
            "daily_activity_cap": 20,
            "rewards": [{"points": 2, "probability_basis_points": 10000}],
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["puzzle_enabled"] is False

    puzzle_response = client.post(
        "/api/v1/admin/puzzles",
        json={
            "business_date": current_business_date().isoformat(),
            "prompt": "What is 2 + 2?",
            "answer": "4",
            "reward_points": 3,
        },
    )
    assert puzzle_response.status_code == 201
    assert "answer_hash" not in puzzle_response.json()
    with test_session_factory() as session:
        assert session.query(AdminAuditLog).count() == 2
