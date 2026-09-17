from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from core.models import Booking, BookingStatus, Court, Sport, Tier, User


@pytest.mark.django_db
def test_accepts_valid_booking_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    booking = Booking.objects.create(
        court=court,
        starts_at="2024-06-01T10:00:00Z",
        ends_at="2024-06-01T11:00:00Z",
        created_by=user,
        status=BookingStatus.ACTIVE,
    )
    assert booking.id is not None
    assert Booking.objects.count() == 1


@pytest.mark.django_db
def test_rejects_duplicate_booking_active_slot_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
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
        created_by=user,
        status=BookingStatus.ACTIVE,
    )
    with (
        pytest.raises(IntegrityError, match="unique_booking_per_court_time"),
        transaction.atomic(),
    ):
        Booking.objects.create(
            court=court,
            starts_at="2024-06-01T10:00:00Z",
            ends_at="2024-06-01T11:00:00Z",
            created_by=user,
            status=BookingStatus.ACTIVE,
        )


@pytest.mark.django_db
def test_accepts_slot_reuse_after_cancellation_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    booking1 = Booking.objects.create(
        court=court,
        starts_at="2024-06-01T10:00:00Z",
        ends_at="2024-06-01T11:00:00Z",
        created_by=user,
        status=BookingStatus.ACTIVE,
    )
    booking1.status = BookingStatus.CANCELLED
    booking1.save()

    booking2 = Booking.objects.create(
        court=court,
        starts_at="2024-06-01T10:00:00Z",
        ends_at="2024-06-01T11:00:00Z",
        created_by=user,
        status=BookingStatus.ACTIVE,
    )
    assert booking2.id is not None
    assert Booking.objects.count() == 2


@pytest.mark.django_db
def test_rejects_duplicate_active_slot_with_400():
    responde = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    responde.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "created_by": user.id,
    }
    response1 = responde.post("/api/v1/bookings/", booking_data)
    assert response1.status_code == 201
    response2 = responde.post("/api/v1/bookings/", booking_data)
    assert response2.status_code == 400


@pytest.mark.django_db
def test_accepts_slot_reuse_after_cancellation_with_201():
    response = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    response.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "created_by": user.id,
    }
    response1 = response.post("/api/v1/bookings/", booking_data)
    assert response1.status_code == 201
    booking_id = response1.data["id"]
    Booking.objects.filter(id=booking_id).update(status=BookingStatus.CANCELLED)
    response2 = response.post("/api/v1/bookings/", booking_data)
    assert response2.status_code == 201


@pytest.mark.django_db
def test_rejects_booking_without_full_hour_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    with (
        pytest.raises(IntegrityError, match="booking_starts_at_full_hour"),
        transaction.atomic(),
    ):
        Booking.objects.create(
            court=court,
            starts_at="2024-06-01T10:30:00Z",
            ends_at="2024-06-01T11:30:00Z",
            created_by=user,
            status=BookingStatus.ACTIVE,
        )


@pytest.mark.django_db
def test_rejects_booking_with_fractional_seconds_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    with (
        pytest.raises(IntegrityError, match="booking_starts_at_full_hour"),
        transaction.atomic(),
    ):
        Booking.objects.create(
            court=court,
            starts_at="2024-06-01T10:00:00.123Z",
            ends_at="2024-06-01T11:00:00.123Z",
            created_by=user,
            status=BookingStatus.ACTIVE,
        )


@pytest.mark.django_db
def test_rejects_booking_with_duration_other_than_one_hour_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    with (
        pytest.raises(IntegrityError, match="booking_slot_lasts_one_hour"),
        transaction.atomic(),
    ):
        Booking.objects.create(
            court=court,
            starts_at="2024-06-01T10:00:00Z",
            ends_at="2024-06-01T12:00:00Z",
            created_by=user,
            status=BookingStatus.ACTIVE,
        )


@pytest.mark.django_db
def test_accepts_back_to_back_bookings_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    booking1 = Booking.objects.create(
        court=court,
        starts_at="2024-06-01T10:00:00Z",
        ends_at="2024-06-01T11:00:00Z",
        created_by=user,
        status=BookingStatus.ACTIVE,
    )
    booking2 = Booking.objects.create(
        court=court,
        starts_at="2024-06-01T11:00:00Z",
        ends_at="2024-06-01T12:00:00Z",
        created_by=user,
        status=BookingStatus.ACTIVE,
    )
    assert booking1.id is not None
    assert booking2.id is not None
    assert Booking.objects.count() == 2


@pytest.mark.django_db
def test_derives_ends_at_one_hour_after_starts_with_201():
    client = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "created_by": user.id,
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.ends_at == datetime(2024, 6, 1, 11, 0, tzinfo=UTC)


@pytest.mark.django_db
def test_rejects_booking_off_the_hour_with_400():
    client = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:30:00Z",
        "created_by": user.id,
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 400
    assert "starts_at" in response.data


@pytest.mark.django_db
def test_rejects_booking_with_fractional_seconds_with_400():
    client = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00.123Z",
        "created_by": user.id,
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 400
    assert "starts_at" in response.data


@pytest.mark.django_db
def test_ignores_client_ends_at_with_201():
    client = APIClient()
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "ends_at": "2024-06-01T12:00:00Z",
        "created_by": user.id,
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.ends_at == datetime(2024, 6, 1, 11, 0, tzinfo=UTC)
