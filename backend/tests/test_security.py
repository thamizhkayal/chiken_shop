def register_customer(client, email="security-customer@example.com"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "full_name": "Security Customer",
            "password": "a-very-long-password",
        },
    )


def test_auth_cookies_are_http_only_and_response_does_not_expose_tokens(client):
    response = register_customer(client)

    assert response.status_code == 201
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()
    cookie_headers = response.headers.get_list("set-cookie")
    assert len(cookie_headers) == 2
    for cookie in cookie_headers:
        assert "HttpOnly" in cookie
        assert "SameSite=lax" in cookie


def test_untrusted_browser_origin_cannot_mutate_auth_state(client):
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://untrusted.example"},
        json={"identifier": "security-customer@example.com", "password": "a-very-long-password"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted request origin"


def test_customer_cannot_access_admin_or_staff_dashboards(client):
    assert register_customer(client).status_code == 201

    assert client.get("/api/v1/admin/dashboard").status_code == 403
    assert client.get("/api/v1/staff/dashboard").status_code == 403
