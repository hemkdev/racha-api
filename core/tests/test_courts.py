from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from core.models import Court, Sport, Tier


@pytest.mark.django_db
def test_creates_court_with_valid_data():
    court = Court.objects.create(
        name="Quadra 1",
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
            name="Quadra 2",
            sport=Sport.SOCCER,
            tier=Tier.BASIC,
            hour_price=Decimal("-50.00"),
        )


@pytest.mark.django_db
def test_rejects_invalid_tier_at_database_level():
    with pytest.raises(IntegrityError), transaction.atomic():
        Court.objects.create(
            name="Quadra 2",
            sport=Sport.SOCCER,
            tier="TOP",
            hour_price=Decimal("50.00"),
        )


@pytest.mark.django_db
def test_rejects_invalid_sport_at_database_level():
    with pytest.raises(IntegrityError), transaction.atomic():
        Court.objects.create(
            name="Quadra 2",
            sport="BEACH_TENNIS",
            tier=Tier.BASIC,
            hour_price=Decimal("50.00"),
        )


@pytest.mark.django_db
def test_list_returns_created_courts():
    Court.objects.create(
        name="Quadra 1",
        sport=Sport.SOCCER,
        tier=Tier.BASIC,
        hour_price=Decimal("100.00"),
    )

    response = APIClient().get("/api/v1/courts/")

    assert response.status_code == 200
    assert len(response.data) == 1


@pytest.mark.django_db
def test_rejects_invalid_sport_with_400():
    response = APIClient().post(
        "/api/v1/courts/",
        {"name": "X", "sport": "BANANA", "tier": "BASIC", "hour_price": "50.00"},
        format="json",
    )

    assert response.status_code == 400
    assert "sport" in response.data
