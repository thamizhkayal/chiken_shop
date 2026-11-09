from datetime import datetime, timedelta, timezone

from app.models.identity import Role, User
from app.models.redemption import RedemptionRequest, RedemptionStatus
from app.models.wallet import Wallet, WalletTransactionType
from app.services.dashboard_service import get_admin_dashboard, get_staff_dashboard
from app.services.wallet_service import record_transaction


def create_customer(db_session) -> User:
    role = db_session.query(Role).filter_by(name="customer").one()
    user = User(
        role_id=role.id,
        email="dashboard-customer@example.com",
        full_name="Dashboard Customer",
        password_hash="unused",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Wallet(user_id=user.id))
    db_session.commit()
    return user


def test_admin_dashboard_reports_customer_wallet_and_redemption_totals(db_session):
    customer = create_customer(db_session)
    record_transaction(
        db_session,
        user_id=customer.id,
        transaction_type=WalletTransactionType.SPIN_REWARD,
        points_delta=400,
        description="Test spin reward",
        reference_id="dashboard-spin-reward",
    )

    now = datetime.now(timezone.utc)
    redemptions = [
        RedemptionRequest(
            user_id=customer.id,
            points=150,
            status=RedemptionStatus.FULFILLED.value,
            idempotency_key="dashboard-fulfilled-001",
            expires_at=now + timedelta(minutes=10),
            fulfilled_grams=150,
            fulfilled_at=now,
        ),
        RedemptionRequest(
            user_id=customer.id,
            points=100,
            status=RedemptionStatus.RESERVED.value,
            idempotency_key="dashboard-reserved-001",
            expires_at=now + timedelta(minutes=10),
        ),
        RedemptionRequest(
            user_id=customer.id,
            points=100,
            status=RedemptionStatus.EXPIRED.value,
            idempotency_key="dashboard-expired-001",
            expires_at=now - timedelta(minutes=10),
        ),
        RedemptionRequest(
            user_id=customer.id,
            points=100,
            status=RedemptionStatus.CANCELLED.value,
            idempotency_key="dashboard-cancelled-001",
            expires_at=now + timedelta(minutes=10),
        ),
    ]
    db_session.add_all(redemptions)
    db_session.commit()

    dashboard = get_admin_dashboard(db_session)

    assert dashboard.total_customers == 1
    assert dashboard.daily_active_customers == 1
    assert dashboard.total_points_issued == 400
    assert dashboard.outstanding_points == 400
    assert dashboard.total_points_redeemed == 150
    assert dashboard.total_chicken_grams_redeemed == 150
    assert dashboard.pending_redemptions == 1
    assert dashboard.completed_redemptions == 1
    assert dashboard.expired_redemptions == 1
    assert dashboard.cancelled_redemptions == 1


def test_staff_dashboard_reports_fulfilment_and_recent_redemptions(db_session):
    customer = create_customer(db_session)
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            RedemptionRequest(
                user_id=customer.id,
                points=200,
                status=RedemptionStatus.FULFILLED.value,
                idempotency_key="staff-dashboard-fulfilled",
                expires_at=now + timedelta(minutes=10),
                fulfilled_grams=180,
                fulfilled_at=now,
            ),
            RedemptionRequest(
                user_id=customer.id,
                points=100,
                status=RedemptionStatus.RESERVED.value,
                idempotency_key="staff-dashboard-reserved",
                expires_at=now + timedelta(minutes=10),
            ),
        ]
    )
    db_session.commit()

    dashboard = get_staff_dashboard(db_session)

    assert dashboard.pending_redemptions == 1
    assert dashboard.fulfilled_today == 1
    assert dashboard.chicken_grams_fulfilled_today == 180
    assert len(dashboard.recent_redemptions) == 2
    assert dashboard.recent_redemptions[0].customer_name == customer.full_name


def test_dashboard_endpoints_require_authentication(client):
    assert client.get("/api/v1/admin/dashboard").status_code == 401
    assert client.get("/api/v1/staff/dashboard").status_code == 401
