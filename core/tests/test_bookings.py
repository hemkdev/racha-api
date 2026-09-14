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
        hour_price=50.00,
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
        hour_price=50.00,
        is_active=True,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Booking.objects.create(
            court=court,
            starts_at="2024-06-01T10:00:00Z",
            ends_at="2024-06-01T11:00:00Z",
            created_by=user,
            status=BookingStatus.ACTIVE,
        )
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
        hour_price=50.00,
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
        hour_price=50.00,
        is_active=True,
    )
    responde.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "ends_at": "2024-06-01T11:00:00Z",
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
        hour_price=50.00,
        is_active=True,
    )
    response.force_authenticate(user=user)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "ends_at": "2024-06-01T11:00:00Z",
        "created_by": user.id,
    }
    response1 = response.post("/api/v1/bookings/", booking_data)
    assert response1.status_code == 201
    booking_id = response1.data["id"]
    Booking.objects.filter(id=booking_id).update(status=BookingStatus.CANCELLED)
    response2 = response.post("/api/v1/bookings/", booking_data)
    assert response2.status_code == 201
