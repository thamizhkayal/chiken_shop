from datetime import datetime, timedelta, timezone

import pytest

from app.models.identity import Role, User
from app.models.wallet import Wallet, WalletTransactionType
from app.services.wallet_service import (
    WalletError,
    award_daily_login_point,
    get_summary,
    record_transaction,
    reconcile_balance,
)


def create_customer(db_session):
    role = db_session.query(Role).filter_by(name="customer").one()
    user = User(
        role_id=role.id,
        email="ledger-customer@example.com",
        full_name="Ledger Customer",
        password_hash="unused",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(Wallet(user_id=user.id))
    db_session.commit()
    return user


def test_ledger_transactions_keep_balance_reconciled_and_non_negative(db_session):
    user = create_customer(db_session)

    record_transaction(
        db_session,
        user_id=user.id,
        transaction_type=WalletTransactionType.SPIN_REWARD,
        points_delta=150,
        description="Daily spin reward",
        reference_id="spin-1",
    )
    record_transaction(
        db_session,
        user_id=user.id,
        transaction_type=WalletTransactionType.REDEMPTION_RESERVATION,
        points_delta=-100,
        description="Redeem 100 grams",
        reference_id="redemption-1",
    )

    assert get_summary(db_session, user.id).balance_points == 50
    assert reconcile_balance(db_session, user.id)

    with pytest.raises(WalletError, match="Insufficient points"):
        record_transaction(
            db_session,
            user_id=user.id,
            transaction_type=WalletTransactionType.REDEMPTION_RESERVATION,
            points_delta=-100,
            description="Redeem another 100 grams",
            reference_id="redemption-2",
        )

    assert get_summary(db_session, user.id).balance_points == 50
    assert reconcile_balance(db_session, user.id)


def test_redemption_reservation_minimum_is_enforced(db_session):
    user = create_customer(db_session)

    with pytest.raises(WalletError, match="at least 100"):
        record_transaction(
            db_session,
            user_id=user.id,
            transaction_type=WalletTransactionType.REDEMPTION_RESERVATION,
            points_delta=-99,
            description="Redeem 99 grams",
        )


def test_daily_login_reward_can_be_earned_again_on_a_later_shop_day(db_session):
    user = create_customer(db_session)
    first_login = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

    assert award_daily_login_point(db_session, user.id, occurred_at=first_login)
    db_session.commit()
    assert not award_daily_login_point(db_session, user.id, occurred_at=first_login + timedelta(hours=2))
    db_session.commit()
    assert award_daily_login_point(db_session, user.id, occurred_at=first_login + timedelta(days=1))
    db_session.commit()

    assert get_summary(db_session, user.id).balance_points == 2
    assert reconcile_balance(db_session, user.id)


def test_duplicate_reference_does_not_change_wallet_balance(db_session):
    user = create_customer(db_session)

    record_transaction(
        db_session,
        user_id=user.id,
        transaction_type=WalletTransactionType.SPIN_REWARD,
        points_delta=25,
        description="Daily spin reward",
        reference_id="same-spin",
    )
    with pytest.raises(WalletError, match="reference already exists"):
        record_transaction(
            db_session,
            user_id=user.id,
            transaction_type=WalletTransactionType.SPIN_REWARD,
            points_delta=25,
            description="Duplicate daily spin reward",
            reference_id="same-spin",
        )

    assert get_summary(db_session, user.id).balance_points == 25
    assert reconcile_balance(db_session, user.id)
