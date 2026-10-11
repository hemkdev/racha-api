from datetime import datetime
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
from core.tests.helpers import create_customer_booking, freeze_now


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
    create_customer_booking(court, user, "2030-06-01T10:00:00Z")
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
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2030-10-01")
    assert response.status_code == 200
    data = response.json()
    assert data["court"] == court.id
    assert data["date"] == "2030-10-01"
    slots = data["slots"]
    assert len(slots) == 14
    assert slots[0]["starts_at"] == "2030-10-01T08:00:00-03:00"
    assert slots[-1]["ends_at"] == "2030-10-01T22:00:00-03:00"
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
    create_customer_booking(court, user, "2030-10-01T13:00:00Z")
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2030-10-01")
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
        starts_at="2030-10-01T13:00:00Z",
        ends_at="2030-10-01T14:00:00Z",
        created_by=staff,
        kind=BookingKind.MAINTENANCE,
        reason="Net repair",
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2030-10-01")
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
    create_customer_booking(
        court, user, "2030-10-01T13:00:00Z", status=BookingStatus.CANCELLED
    )
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2030-10-01")
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
        (other_court, "2030-10-01T13:00:00Z"),
        (court, "2030-10-02T13:00:00Z"),
        (court, "2030-10-01T00:00:00Z"),
    ]:
        create_customer_booking(booking_court, user, starts_at)
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2030-10-01")
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
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2030-10-01")
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
        ("2030-10-01T08:00:00-03:00", Decimal("50.00")),
        ("2030-10-01T17:00:00-03:00", Decimal("50.00")),
        ("2030-10-01T18:00:00-03:00", Decimal("75.00")),
        ("2030-10-01T21:00:00-03:00", Decimal("75.00")),
        ("2030-10-01T20:00:00Z", Decimal("50.00")),
        ("2030-10-01T21:00:00Z", Decimal("75.00")),
        ("2030-10-02T00:00:00Z", Decimal("75.00")),
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
    response = client.get(f"/api/v1/courts/{court.id}/slots/?date=2030-10-01")
    assert response.status_code == 200
    prices = [slot["price"] for slot in response.json()["slots"]]
    assert prices == ["50.00"] * 10 + ["75.00"] * 4


def create_staff_client():
    client = APIClient()
    staff = User.objects.create(
        username="staff", email="staff@example.com", role=Role.STAFF
    )
    client.force_authenticate(user=staff)
    return client, staff


def create_volleyball_court():
    return Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("hour_price", ["50.50", "0.50", "9999.50"])
def test_accepts_price_in_half_real_steps_at_database_level(hour_price):
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.SOCCER,
        tier=Tier.BASIC,
        hour_price=Decimal(hour_price),
    )
    assert court.pk is not None


@pytest.mark.django_db
@pytest.mark.parametrize("hour_price", ["49.99", "50.25", "0.01"])
def test_rejects_price_off_half_real_steps_at_database_level(hour_price):
    with (
        pytest.raises(IntegrityError, match="court_hour_price_half_steps"),
        transaction.atomic(),
    ):
        Court.objects.create(
            name="Court 1",
            sport=Sport.SOCCER,
            tier=Tier.BASIC,
            hour_price=Decimal(hour_price),
        )


@pytest.mark.django_db
def test_rejects_price_off_half_real_steps_on_creation_with_400():
    client, _ = create_staff_client()
    response = client.post(
        "/api/v1/courts/",
        {"name": "X", "sport": "SOCCER", "tier": "BASIC", "hour_price": "49.99"},
        format="json",
    )
    assert response.status_code == 400
    assert "hour_price" in response.data
    assert not Court.objects.exists()


@pytest.mark.django_db
def test_rejects_price_off_half_real_steps_on_update_with_400():
    client, _ = create_staff_client()
    court = create_volleyball_court()
    response = client.patch(f"/api/v1/courts/{court.id}/", {"hour_price": "49.99"})
    assert response.status_code == 400
    assert "hour_price" in response.data
    court.refresh_from_db()
    assert court.hour_price == Decimal("50.00")


@pytest.mark.django_db
@pytest.mark.parametrize("kind", [BookingKind.CUSTOMER, BookingKind.MAINTENANCE])
def test_rejects_deactivating_court_with_future_booking_with_409(kind):
    client, staff = create_staff_client()
    court = create_volleyball_court()
    if kind == BookingKind.CUSTOMER:
        customer = User.objects.create(username="customer", role=Role.CUSTOMER)
        create_customer_booking(court, customer, "2030-10-01T09:00:00-03:00")
    else:
        Booking.objects.create(
            court=court,
            starts_at=datetime.fromisoformat("2030-10-01T09:00:00-03:00"),
            ends_at=datetime.fromisoformat("2030-10-01T10:00:00-03:00"),
            created_by=staff,
            kind=BookingKind.MAINTENANCE,
            reason="Net repair",
        )
    with freeze_now("2030-10-01T08:10:00"):
        response = client.patch(f"/api/v1/courts/{court.id}/", {"is_active": False})
    assert response.status_code == 409
    court.refresh_from_db()
    assert court.is_active is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "starts_at, status",
    [
        ("2030-10-01T08:00:00-03:00", BookingStatus.ACTIVE),
        ("2030-10-01T09:00:00-03:00", BookingStatus.CANCELLED),
    ],
    ids=["started_booking", "cancelled_future_booking"],
)
def test_deactivates_court_without_future_active_booking_with_200(starts_at, status):
    client, _ = create_staff_client()
    court = create_volleyball_court()
    customer = User.objects.create(username="customer", role=Role.CUSTOMER)
    create_customer_booking(court, customer, starts_at, status=status)
    with freeze_now("2030-10-01T08:10:00"):
        response = client.patch(f"/api/v1/courts/{court.id}/", {"is_active": False})
    assert response.status_code == 200
    court.refresh_from_db()
    assert court.is_active is False


@pytest.mark.django_db
def test_updates_court_with_future_booking_when_not_deactivating_with_200():
    client, _ = create_staff_client()
    court = create_volleyball_court()
    customer = User.objects.create(username="customer", role=Role.CUSTOMER)
    create_customer_booking(court, customer, "2030-10-01T09:00:00-03:00")
    with freeze_now("2030-10-01T08:10:00"):
        response = client.patch(f"/api/v1/courts/{court.id}/", {"hour_price": "60.00"})
    assert response.status_code == 200
    court.refresh_from_db()
    assert court.hour_price == Decimal("60.00")
