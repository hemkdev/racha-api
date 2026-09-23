from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from core.models import Court, Role, Sport, Tier, User


@pytest.mark.django_db
def test_accepts_valid_court_at_database_level():
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.SOCCER,
        tier=Tier.BASIC,
        hour_price=Decimal("100.00"),
    )

    assert court.pk is not None
    assert Court.objects.count() == 1


@pytest.mark.django_db
def test_rejects_negative_price_at_database_level():
    with pytest.raises(IntegrityError), transaction.atomic():
        Court.objects.create(
            name="Court 2",
            sport=Sport.SOCCER,
            tier=Tier.BASIC,
            hour_price=Decimal("-50.00"),
        )


@pytest.mark.django_db
def test_rejects_invalid_tier_at_database_level():
    with pytest.raises(IntegrityError), transaction.atomic():
        Court.objects.create(
            name="Court 2",
            sport=Sport.SOCCER,
            tier="TOP",
            hour_price=Decimal("50.00"),
        )


@pytest.mark.django_db
def test_rejects_invalid_sport_at_database_level():
    with pytest.raises(IntegrityError), transaction.atomic():
        Court.objects.create(
            name="Court 2",
            sport="BEACH_TENNIS",
            tier=Tier.BASIC,
            hour_price=Decimal("50.00"),
        )


@pytest.mark.django_db
def test_list_courts_with_200():
    Court.objects.create(
        name="Court 1",
        sport=Sport.SOCCER,
        tier=Tier.BASIC,
        hour_price=Decimal("100.00"),
    )

    response = APIClient().get("/api/v1/courts/")

    assert response.status_code == 200
    assert len(response.data) == 1


@pytest.mark.django_db
def test_rejects_invalid_sport_with_400():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.STAFF,
    )
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/courts/",
        {"name": "X", "sport": "BANANA", "tier": "BASIC", "hour_price": "50.00"},
        format="json",
    )

    assert response.status_code == 400
    assert "sport" in response.data


@pytest.mark.django_db
def test_rejects_negative_price_with_400():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.STAFF,
    )
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/courts/",
        {"name": "X", "sport": "SOCCER", "tier": "BASIC", "hour_price": "-50.00"},
        format="json",
    )

    assert response.status_code == 400
    assert "hour_price" in response.data


@pytest.mark.django_db
def test_rejects_zero_price_with_400():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.STAFF,
    )
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/courts/",
        {"name": "X", "sport": "SOCCER", "tier": "BASIC", "hour_price": "0.00"},
        format="json",
    )

    assert response.status_code == 400
    assert "hour_price" in response.data
