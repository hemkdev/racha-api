from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient

from core.models import Booking, BookingStatus, Court, Role, Sport, Tier, User


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
    }
    response1 = client.post("/api/v1/bookings/", booking_data)
    assert response1.status_code == 201
    response2 = client.post("/api/v1/bookings/", booking_data)
    assert response2.status_code == 400


@pytest.mark.django_db
def test_accepts_slot_reuse_after_cancellation_with_201():
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
    }
    response1 = client.post("/api/v1/bookings/", booking_data)
    assert response1.status_code == 201
    booking_id = response1.data["id"]
    Booking.objects.filter(id=booking_id).update(status=BookingStatus.CANCELLED)
    response2 = client.post("/api/v1/bookings/", booking_data)
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
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.ends_at == datetime(2024, 6, 1, 11, 0, tzinfo=UTC)


@pytest.mark.django_db
def test_rejects_invalid_status_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    with (
        pytest.raises(IntegrityError, match="booking_status_valid"),
        transaction.atomic(),
    ):
        Booking.objects.create(
            court=court,
            starts_at="2024-06-01T10:00:00Z",
            ends_at="2024-06-01T11:00:00Z",
            created_by=user,
            status="PENDING",
        )


@pytest.mark.django_db
def test_accepts_booking_without_user_at_database_level():
    staff = User.objects.create_user(
        username="staffuser", password="testpass", role=Role.STAFF
    )
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
        created_by=staff,
        status=BookingStatus.ACTIVE,
    )
    assert Booking.objects.get(id=booking.id).user is None


@pytest.mark.django_db
def test_accepts_booking_created_by_staff_for_a_customer_at_database_level():
    staff = User.objects.create_user(
        username="staffuser", password="testpass", role=Role.STAFF
    )
    customer = User.objects.create_user(
        username="customeruser", password="testpass", role=Role.CUSTOMER
    )
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
        user=customer,
        created_by=staff,
        status=BookingStatus.ACTIVE,
    )
    assert Booking.objects.get(id=booking.id).user == customer
    assert customer.bookings.count() == 1
    assert staff.bookings.count() == 0
    assert staff.created_bookings.count() == 1


@pytest.mark.django_db
def test_rejects_anonymous_booking_list_with_401():
    client = APIClient()
    response = client.get("/api/v1/bookings/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_lists_only_own_bookings_for_customer_with_200():
    client = APIClient()
    customer1 = User.objects.create_user(
        username="customer1", password="testpass", role=Role.CUSTOMER
    )
    customer2 = User.objects.create_user(
        username="customer2", password="testpass", role=Role.CUSTOMER
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=customer1)
    response1 = client.post(
        "/api/v1/bookings/", {"court": court.id, "starts_at": "2024-06-01T10:00:00Z"}
    )
    client.force_authenticate(user=customer2)
    client.post(
        "/api/v1/bookings/", {"court": court.id, "starts_at": "2024-06-01T11:00:00Z"}
    )
    client.force_authenticate(user=customer1)
    response = client.get("/api/v1/bookings/")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == response1.data["id"]


@pytest.mark.django_db
def test_sets_user_to_request_customer_with_201():
    client = APIClient()
    customer = User.objects.create_user(
        username="customer", password="testpass", role=Role.CUSTOMER
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=customer)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.user == customer
    assert booking.created_by == customer


@pytest.mark.django_db
def test_rejects_user_in_body_for_customer_with_400():
    client = APIClient()
    customer1 = User.objects.create_user(
        username="customer1", password="testpass", role=Role.CUSTOMER
    )
    customer2 = User.objects.create_user(
        username="customer2", password="testpass", role=Role.CUSTOMER
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=customer1)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "user": customer2.id,
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 400
    assert "user" in response.data
    assert Booking.objects.count() == 0


@pytest.mark.django_db
def test_accepts_user_in_body_for_staff_with_201():
    client = APIClient()
    staff = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    customer = User.objects.create_user(
        username="customer", password="testpass", role=Role.CUSTOMER
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=staff)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "user": customer.id,
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.user == customer


@pytest.mark.django_db
def test_leaves_user_as_null_when_no_user_is_specified_for_staff_with_201():
    client = APIClient()
    staff = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=staff)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.user is None


@pytest.mark.django_db
def test_ignores_created_by_in_body_with_201():
    client = APIClient()
    staff1 = User.objects.create_user(
        username="staff1", password="testpass", role=Role.STAFF
    )
    staff2 = User.objects.create_user(
        username="staff2", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=staff1)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
        "created_by": staff2.id,
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.created_by == staff1


@pytest.mark.django_db
def test_rejects_booking_delete_with_405():
    client = APIClient()
    staff = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=staff)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking_id = response.data["id"]
    delete_response = client.delete(f"/api/v1/bookings/{booking_id}/")
    assert delete_response.status_code == 405
    assert Booking.objects.filter(id=booking_id).exists()


@pytest.mark.django_db
def test_rejects_booking_update_with_405():
    client = APIClient()
    staff = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=staff)
    booking_data = {
        "court": court.id,
        "starts_at": "2024-06-01T10:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking_id = response.data["id"]
    update_data = {
        "starts_at": "2024-06-01T11:00:00Z",
    }
    put_response = client.put(f"/api/v1/bookings/{booking_id}/", update_data)
    assert put_response.status_code == 405
    update_response = client.patch(f"/api/v1/bookings/{booking_id}/", update_data)
    assert update_response.status_code == 405
    booking = Booking.objects.get(id=booking_id)
    assert booking.starts_at == datetime(2024, 6, 1, 10, tzinfo=UTC)
