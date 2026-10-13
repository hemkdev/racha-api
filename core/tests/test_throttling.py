import pytest
from rest_framework.test import APIClient

WRONG_LOGIN = {"username": "nobody", "password": "wrong"}


@pytest.mark.django_db
def test_throttles_anonymous_requests_after_sixty_per_minute():
    client = APIClient()
    for _ in range(60):
        assert client.get("/api/v1/courts/").status_code == 200
    assert client.get("/api/v1/courts/").status_code == 429


@pytest.mark.django_db
def test_throttles_token_requests_after_five_per_minute():
    client = APIClient()
    for _ in range(5):
        response = client.post("/api/v1/token/", WRONG_LOGIN, format="json")
        assert response.status_code == 401
    response = client.post("/api/v1/token/", WRONG_LOGIN, format="json")
    assert response.status_code == 429


@pytest.mark.django_db
def test_identifies_clients_by_the_address_the_proxy_appended():
    # Only the last X-Forwarded-For entry comes from nginx; anything before it is
    # whatever the client sent, so changing it must not open a new bucket.
    client = APIClient()
    for _ in range(5):
        client.post(
            "/api/v1/token/",
            WRONG_LOGIN,
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.1, 203.0.113.7",
        )
    spoofed = client.post(
        "/api/v1/token/",
        WRONG_LOGIN,
        format="json",
        HTTP_X_FORWARDED_FOR="198.51.100.2, 203.0.113.7",
    )
    assert spoofed.status_code == 429
    other = client.post(
        "/api/v1/token/",
        WRONG_LOGIN,
        format="json",
        HTTP_X_FORWARDED_FOR="203.0.113.8",
    )
    assert other.status_code == 401
