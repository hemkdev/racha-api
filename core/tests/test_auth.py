import pytest
from rest_framework.test import APIClient

from core.models import Role, User


@pytest.mark.django_db
def test_issues_token_pair_with_200():
    User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    response = client.post(
        "/api/v1/token/",
        {"username": "testuser", "password": "testpassword"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_rejects_invalid_credentials_with_401():
    User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    response = client.post(
        "/api/v1/token/",
        {"username": "testuser", "password": "wrongpassword"},
        format="json",
    )
    assert response.status_code == 401
    assert "access" not in response.data
    assert "refresh" not in response.data


@pytest.mark.django_db
def test_refresh_token_with_200():
    User.objects.create_user(username="testuser", password="testpassword")
    client = APIClient()
    response1 = client.post(
        "/api/v1/token/",
        {"username": "testuser", "password": "testpassword"},
        format="json",
    )
    refresh_token = response1.data["refresh"]
    response2 = client.post(
        "/api/v1/token/refresh/",
        {"refresh": refresh_token},
        format="json",
    )
    assert response2.status_code == 200
    assert "access" in response2.data


@pytest.mark.django_db
def test_accepts_bearer_token_court_creation_with_201():
    User.objects.create_user(
        username="testuser", password="testpassword", role=Role.STAFF
    )
    client = APIClient()
    response1 = client.post(
        "/api/v1/token/",
        {"username": "testuser", "password": "testpassword"},
        format="json",
    )
    access_token = response1.data["access"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    response2 = client.post(
        "/api/v1/courts/",
        {"name": "X", "sport": "SOCCER", "tier": "BASIC", "hour_price": "50.00"},
        format="json",
    )
    assert response2.status_code == 201
