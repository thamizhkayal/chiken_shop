def test_customer_can_register_and_read_profile(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "customer@example.com",
            "full_name": "Casey Customer",
            "password": "a-very-long-password",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "customer"
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    profile = client.get("/api/v1/users/me")
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Casey Customer"


def test_refresh_rotates_token_and_rejects_reuse(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@example.com",
            "full_name": "Riley Refresh",
            "password": "a-very-long-password",
        },
    )
    old_refresh = client.cookies.get("refresh_token")

    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    new_refresh = client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    client.cookies.set("refresh_token", old_refresh)
    reused = client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401


def test_registration_requires_contact_and_duplicate_is_rejected(client):
    missing_contact = client.post(
        "/api/v1/auth/register",
        json={"full_name": "No Contact", "password": "a-very-long-password"},
    )
    assert missing_contact.status_code == 422

    payload = {
        "email": "duplicate@example.com",
        "full_name": "Duplicate User",
        "password": "a-very-long-password",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_invalid_login_does_not_authenticate(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "unknown@example.com", "password": "not-the-password"},
    )
    assert response.status_code == 401


def test_customer_can_login_and_read_wallet(client):
    payload = {
        "email": "wallet-login@example.com",
        "full_name": "Wallet Customer",
        "password": "a-very-long-password",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201

    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": payload["email"], "password": payload["password"]},
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    wallet = client.get("/api/v1/wallet")
    assert wallet.status_code == 200
    assert wallet.json() == {
        "balance_points": 1,
        "raw_chicken_grams": 1,
        "minimum_redemption_points": 100,
        "points_to_grams_rule": "1 point = 1 gram of raw chicken",
    }
    transactions = client.get("/api/v1/wallet/transactions").json()
    assert len(transactions) == 1
    assert transactions[0]["transaction_type"] == "daily_login_reward"


def test_successful_login_awards_one_point_once_per_day(client):
    payload = {
        "email": "daily-login@example.com",
        "full_name": "Daily Login",
        "password": "a-very-long-password",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    failed_login = client.post(
        "/api/v1/auth/login",
        json={"identifier": payload["email"], "password": "wrong-password"},
    )
    assert failed_login.status_code == 401

    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": payload["email"], "password": payload["password"]},
        )
        assert response.status_code == 200

    assert client.post("/api/v1/auth/refresh").status_code == 200
    wallet = client.get("/api/v1/wallet")
    assert wallet.status_code == 200
    assert wallet.json()["balance_points"] == 1
    transactions = client.get("/api/v1/wallet/transactions").json()
    assert len(transactions) == 1
    assert transactions[0]["transaction_type"] == "daily_login_reward"
    assert transactions[0]["points_delta"] == 1


def test_customer_cannot_access_admin_route(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-admin@example.com",
            "full_name": "Customer",
            "password": "a-very-long-password",
        },
    )
    response = client.get("/api/v1/admin/health")
    assert response.status_code == 403
