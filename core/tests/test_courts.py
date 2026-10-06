from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from core.models import (
    Booking,
    BookingKind,
    BookingStatus,
    Court,
    Role,
    Sport,
    Tier,
    User,
)


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


@pytest.mark.django_db
def test_rejects_non_staff_user_with_403():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.CUSTOMER,
    )
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/courts/",
        {"name": "X", "sport": "SOCCER", "tier": "BASIC", "hour_price": "50.00"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_rejects_anonymous_user_with_401():
    client = APIClient()
    response = client.post(
        "/api/v1/courts/",
        {"name": "X", "sport": "SOCCER", "tier": "BASIC", "hour_price": "50.00"},
        format="json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_deactivates_court_as_staff_with_200():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.STAFF,
    )
    client.force_authenticate(user=user)
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    response = client.patch(f"/api/v1/courts/{court.id}/", {"is_active": False})
    assert response.status_code == 200
    court.refresh_from_db()
    assert court.is_active is False


@pytest.mark.django_db
def test_rejects_court_deactivation_as_customer_with_403():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.CUSTOMER,
    )
    client.force_authenticate(user=user)
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    response = client.patch(f"/api/v1/courts/{court.id}/", {"is_active": False})
    assert response.status_code == 403
    court.refresh_from_db()
    assert court.is_active is True


@pytest.mark.django_db
def test_rejects_deleting_court_with_bookings_with_409():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.STAFF,
    )
    client.force_authenticate(user=user)
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    Booking.objects.create(
        court=court,
        starts_at="2024-06-01T10:00:00Z",
        ends_at="2024-06-01T11:00:00Z",
        user=user,
        created_by=user,
    )
    response = client.delete(f"/api/v1/courts/{court.id}/")
    assert response.status_code == 409
    assert Court.objects.filter(id=court.id).exists()


@pytest.mark.django_db
def test_accepts_deleting_court_without_bookings_with_204():
    client = APIClient()
    user = User.objects.create(
        username="testuser",
        email="testuser@example.com",
        role=Role.STAFF,
    )
    client.force_authenticate(user=user)
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    response = client.delete(f"/api/v1/courts/{court.id}/")
    assert response.status_code == 204
    assert not Court.objects.filter(id=court.id).exists()


@pytest.mark.django_db
def test_lists_public_schedule_with_200():
    client = APIClient()
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2026-10-01")
    assert response.status_code == 200
    data = response.json()
    assert data["court"] == court.id
    assert data["date"] == "2026-10-01"
    slots = data["slots"]
    assert len(slots) == 14
    assert slots[0]["starts_at"] == "2026-10-01T08:00:00-03:00"
    assert slots[-1]["ends_at"] == "2026-10-01T22:00:00-03:00"
    assert all(slot["available"] for slot in slots)
    assert all(
        set(slot) == {"starts_at", "ends_at", "available", "price"} for slot in slots
    )


@pytest.mark.django_db
def test_list_shows_booked_slots_as_unavailable_with_200():
    client = APIClient()
    user = User.objects.create(username="testuser")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    Booking.objects.create(
        court=court,
        starts_at="2026-10-01T13:00:00Z",
        ends_at="2026-10-01T14:00:00Z",
        user=user,
        created_by=user,
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2026-10-01")
    assert response.status_code == 200
    availability = [slot["available"] for slot in response.json()["slots"]]
    assert availability == [True, True, False] + [True] * 11


@pytest.mark.django_db
def test_list_shows_maintenance_slots_as_unavailable_with_200():
    client = APIClient()
    staff = User.objects.create(username="staff", role=Role.STAFF)
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    Booking.objects.create(
        court=court,
        starts_at="2026-10-01T13:00:00Z",
        ends_at="2026-10-01T14:00:00Z",
        created_by=staff,
        kind=BookingKind.MAINTENANCE,
        reason="Net repair",
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2026-10-01")
    assert response.status_code == 200
    availability = [slot["available"] for slot in response.json()["slots"]]
    assert availability == [True, True, False] + [True] * 11


@pytest.mark.django_db
def test_cancelled_bookings_do_not_block_slots_with_200():
    client = APIClient()
    user = User.objects.create(username="testuser")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    Booking.objects.create(
        court=court,
        starts_at="2026-10-01T13:00:00Z",
        ends_at="2026-10-01T14:00:00Z",
        user=user,
        created_by=user,
        status=BookingStatus.CANCELLED,
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2026-10-01")
    assert response.status_code == 200
    availability = [slot["available"] for slot in response.json()["slots"]]
    assert availability == [True] * 14


@pytest.mark.django_db
def test_ignores_bookings_from_other_courts_and_days_with_200():
    client = APIClient()
    user = User.objects.create(username="testuser")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    other_court = Court.objects.create(
        name="Court 2",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    for booking_court, starts_at in [
        (other_court, "2026-10-01T13:00:00Z"),
        (court, "2026-10-02T13:00:00Z"),
        (court, "2026-10-01T00:00:00Z"),
    ]:
        Booking.objects.create(
            court=booking_court,
            starts_at=starts_at,
            ends_at=datetime.fromisoformat(starts_at) + timedelta(hours=1),
            user=user,
            created_by=user,
        )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2026-10-01")
    assert response.status_code == 200
    availability = [slot["available"] for slot in response.json()["slots"]]
    assert availability == [True] * 14


@pytest.mark.django_db
def test_rejects_slots_of_inactive_court_with_404():
    client = APIClient()
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=False,
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2026-10-01")
    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("query", ["", "?date=abc"])
def test_rejects_slots_without_valid_date_with_400(query):
    client = APIClient()
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/{query}")
    assert response.status_code == 400
    assert "date" in response.data


@pytest.mark.parametrize(
    "starts_at, expected",
    [
        ("2026-10-01T08:00:00-03:00", Decimal("50.00")),
        ("2026-10-01T17:00:00-03:00", Decimal("50.00")),
        ("2026-10-01T18:00:00-03:00", Decimal("75.00")),
        ("2026-10-01T21:00:00-03:00", Decimal("75.00")),
        ("2026-10-01T20:00:00Z", Decimal("50.00")),
        ("2026-10-01T21:00:00Z", Decimal("75.00")),
        ("2026-10-02T00:00:00Z", Decimal("75.00")),
    ],
)
def test_prices_peak_slots_by_local_hour(starts_at, expected):
    court = Court(hour_price=Decimal("50.00"))
    assert court.price_at(datetime.fromisoformat(starts_at)) == expected


@pytest.mark.django_db
def test_list_shows_slot_prices_with_200():
    client = APIClient()
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2026-10-01")
    assert response.status_code == 200
    prices = [slot["price"] for slot in response.json()["slots"]]
    assert prices == ["50.00"] * 10 + ["75.00"] * 4
