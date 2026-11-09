from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.security import create_token
from app.models.activities import AdminAuditLog
from app.models.identity import Role, User
from app.models.redemption import RedemptionQrToken, RedemptionRequest, RedemptionStatus
from app.models.wallet import Wallet, WalletTransactionType
from app.services import redemption_service
from app.services.redemption_service import RedemptionError
from app.services.wallet_service import get_summary, record_transaction, reconcile_balance


def create_account(db_session, *, role_name: str, email: str) -> User:
    role = db_session.query(Role).filter_by(name=role_name).one()
    user = User(
        role_id=role.id,
        email=email,
        full_name=email.split("@")[0].title(),
        password_hash="unused",
    )
    db_session.add(user)
    db_session.flush()
    if role_name == "customer":
        db_session.add(Wallet(user_id=user.id))
    db_session.commit()
    return user


def add_points(db_session, user: User, points: int) -> None:
    record_transaction(
        db_session,
        user_id=user.id,
        transaction_type=WalletTransactionType.SPIN_REWARD,
        points_delta=points,
        description="Test wallet funding",
        reference_id=f"funding-{uuid4()}",
    )


def get_raw_token(db_session, redemption: RedemptionRequest) -> str:
    token_record = db_session.scalar(
        select(RedemptionQrToken).where(RedemptionQrToken.redemption_id == redemption.id)
    )
    assert token_record is not None
    return redemption_service._derive_token(redemption.id, token_record.id)


def test_redemption_reserves_points_and_uses_opaque_qr_token(db_session):
    customer = create_account(db_session, role_name="customer", email="redeem@example.com")
    add_points(db_session, customer, 350)

    redemption, qr_svg = redemption_service.create_redemption(
        db_session,
        customer.id,
        points=250,
        idempotency_key="reserve-250-points-001",
    )

    assert redemption.status == RedemptionStatus.RESERVED.value
    assert redemption.points == 250
    assert "<svg" in qr_svg
    assert get_summary(db_session, customer.id).balance_points == 100
    assert reconcile_balance(db_session, customer.id)

    token_record = db_session.scalar(
        select(RedemptionQrToken).where(RedemptionQrToken.redemption_id == redemption.id)
    )
    token = get_raw_token(db_session, redemption)
    assert token_record is not None
    assert token not in token_record.token_hash
    assert len(token_record.token_hash) == 64


def test_idempotent_reservation_does_not_debit_twice(db_session):
    customer = create_account(db_session, role_name="customer", email="idempotent@example.com")
    add_points(db_session, customer, 250)

    first, first_qr = redemption_service.create_redemption(
        db_session, customer.id, points=200, idempotency_key="same-reservation-key-001"
    )
    second, second_qr = redemption_service.create_redemption(
        db_session, customer.id, points=200, idempotency_key="same-reservation-key-001"
    )

    assert first.id == second.id
    assert first_qr == second_qr
    assert get_summary(db_session, customer.id).balance_points == 50
    assert db_session.query(RedemptionRequest).filter_by(user_id=customer.id).count() == 1


def test_redemption_validates_minimum_and_available_balance(db_session):
    customer = create_account(db_session, role_name="customer", email="limits@example.com")
    add_points(db_session, customer, 99)

    with pytest.raises(RedemptionError, match="at least 100"):
        redemption_service.create_redemption(
            db_session, customer.id, points=99, idempotency_key="under-minimum-key-001"
        )
    with pytest.raises(RedemptionError, match="Insufficient points"):
        redemption_service.create_redemption(
            db_session, customer.id, points=100, idempotency_key="insufficient-key-001"
        )

    assert get_summary(db_session, customer.id).balance_points == 99
    assert db_session.query(RedemptionRequest).filter_by(user_id=customer.id).count() == 0


def test_customer_cancellation_refunds_once_and_revokes_qr(db_session):
    customer = create_account(db_session, role_name="customer", email="cancel@example.com")
    add_points(db_session, customer, 200)
    redemption, _ = redemption_service.create_redemption(
        db_session, customer.id, points=150, idempotency_key="cancel-reservation-key-001"
    )
    token = get_raw_token(db_session, redemption)

    cancelled, refunded = redemption_service.cancel_redemption(db_session, customer.id, redemption.id)

    assert cancelled.status == RedemptionStatus.CANCELLED.value
    assert refunded == 150
    assert get_summary(db_session, customer.id).balance_points == 200
    assert reconcile_balance(db_session, customer.id)
    with pytest.raises(RedemptionError, match="Only an active"):
        redemption_service.cancel_redemption(db_session, customer.id, redemption.id)
    with pytest.raises(RedemptionError, match="already been used or replaced"):
        redemption_service.verify_staff_token(db_session, token, staff_user_id=customer.id)


def test_expired_reservation_is_refunded_when_customer_views_history(db_session):
    customer = create_account(db_session, role_name="customer", email="expire@example.com")
    add_points(db_session, customer, 300)
    created_at = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
    redemption, _ = redemption_service.create_redemption(
        db_session,
        customer.id,
        points=200,
        idempotency_key="expired-reservation-key-001",
        now=created_at,
    )

    records = redemption_service.list_customer_redemptions(
        db_session, customer.id, now=created_at + timedelta(minutes=16)
    )

    assert records[0].status == RedemptionStatus.EXPIRED.value
    assert get_summary(db_session, customer.id).balance_points == 300
    assert reconcile_balance(db_session, customer.id)


def test_new_reservation_expires_and_refunds_older_reservation_first(db_session):
    customer = create_account(db_session, role_name="customer", email="rebook@example.com")
    add_points(db_session, customer, 300)
    created_at = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
    first, _ = redemption_service.create_redemption(
        db_session,
        customer.id,
        points=250,
        idempotency_key="first-reservation-key-001",
        now=created_at,
    )

    second, _ = redemption_service.create_redemption(
        db_session,
        customer.id,
        points=200,
        idempotency_key="second-reservation-key-001",
        now=created_at + timedelta(minutes=16),
    )

    assert first.status == RedemptionStatus.EXPIRED.value
    assert second.status == RedemptionStatus.RESERVED.value
    assert get_summary(db_session, customer.id).balance_points == 100
    assert reconcile_balance(db_session, customer.id)


def test_fulfillment_limits_weight_refunds_unused_points_and_is_single_use(db_session):
    customer = create_account(db_session, role_name="customer", email="fulfill-customer@example.com")
    staff = create_account(db_session, role_name="staff", email="fulfill-staff@example.com")
    add_points(db_session, customer, 300)
    redemption, _ = redemption_service.create_redemption(
        db_session, customer.id, points=250, idempotency_key="fulfill-reservation-key-001"
    )
    token = get_raw_token(db_session, redemption)

    with pytest.raises(RedemptionError, match="cannot exceed"):
        redemption_service.fulfill_redemption(db_session, staff.id, token, grams=251)
    assert get_summary(db_session, customer.id).balance_points == 50

    verified = redemption_service.verify_staff_token(
        db_session, token, staff_user_id=staff.id
    )
    assert verified.redemption.id == redemption.id
    assert verified.customer_name == customer.full_name

    result = redemption_service.fulfill_redemption(db_session, staff.id, token, grams=200)

    assert result.redemption.status == RedemptionStatus.FULFILLED.value
    assert result.redemption.fulfilled_grams == 200
    assert result.refunded_points == 50
    assert get_summary(db_session, customer.id).balance_points == 100
    assert reconcile_balance(db_session, customer.id)
    with pytest.raises(RedemptionError, match="already been used"):
        redemption_service.fulfill_redemption(db_session, staff.id, token, grams=200)


def test_expired_qr_verification_refunds_and_rejects_token(db_session):
    customer = create_account(db_session, role_name="customer", email="expired-scan@example.com")
    staff = create_account(db_session, role_name="staff", email="expired-staff@example.com")
    add_points(db_session, customer, 200)
    created_at = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
    redemption, _ = redemption_service.create_redemption(
        db_session,
        customer.id,
        points=100,
        idempotency_key="expired-qr-key-001",
        now=created_at,
    )
    token = get_raw_token(db_session, redemption)

    with pytest.raises(RedemptionError, match="expired"):
        redemption_service.fulfill_redemption(
            db_session,
            staff.id,
            token,
            grams=100,
            now=created_at + timedelta(minutes=16),
        )

    assert redemption.status == RedemptionStatus.EXPIRED.value
    assert get_summary(db_session, customer.id).balance_points == 200
    assert reconcile_balance(db_session, customer.id)


def test_qr_refresh_revokes_previous_code(db_session):
    customer = create_account(db_session, role_name="customer", email="refresh-qr@example.com")
    add_points(db_session, customer, 100)
    redemption, _ = redemption_service.create_redemption(
        db_session, customer.id, points=100, idempotency_key="refresh-qr-key-001"
    )
    old_token = get_raw_token(db_session, redemption)

    _, refreshed_qr = redemption_service.refresh_qr(db_session, customer.id, redemption.id)

    assert "<svg" in refreshed_qr
    with pytest.raises(RedemptionError, match="replaced"):
        redemption_service.verify_staff_token(
            db_session, old_token, staff_user_id=customer.id
        )


def test_redemption_api_enforces_customer_and_staff_roles(client, test_session_factory):
    with test_session_factory() as db:
        customer = create_account(db, role_name="customer", email="api-redeem@example.com")
        staff = create_account(db, role_name="staff", email="api-staff@example.com")
        add_points(db, customer, 180)

        def auth_header(user: User) -> dict[str, str]:
            token, _ = create_token(
                user_id=user.id,
                token_type="access",
                expires_delta=timedelta(minutes=5),
                jti=uuid4().hex,
            )
            return {"Authorization": f"Bearer {token}"}

        customer_headers = auth_header(customer)
        staff_headers = auth_header(staff)
        reserved = client.post(
            "/api/v1/redemptions",
            headers={**customer_headers, "Idempotency-Key": "api-redemption-key-001"},
            json={"points": 150},
        )
        assert reserved.status_code == 201
        assert "<svg" in reserved.json()["qr_svg"]
        redemption_id = reserved.json()["id"]
        record = db.get(RedemptionRequest, UUID(redemption_id))
        assert record is not None
        qr_token = get_raw_token(db, record)

        denied = client.post(
            "/api/v1/staff/redemptions/verify",
            headers=customer_headers,
            json={"token": qr_token},
        )
        assert denied.status_code == 403
        verified = client.post(
            "/api/v1/staff/redemptions/verify",
            headers=staff_headers,
            json={"token": qr_token},
        )
        assert verified.status_code == 200
        fulfilled = client.post(
            "/api/v1/staff/redemptions/fulfill",
            headers=staff_headers,
            json={"token": qr_token, "grams": 130},
        )
        assert fulfilled.status_code == 200
        assert fulfilled.json()["refunded_points"] == 20
        assert db.query(AdminAuditLog).filter_by(
            entity_id=redemption_id, actor_user_id=staff.id
        ).count() == 2
