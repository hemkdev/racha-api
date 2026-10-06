from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from rest_framework.test import APIClient

from core.models import (
    Booking,
    BookingKind,
    BookingStatus,
    Court,
    Order,
    OrderStatus,
    Role,
    Sport,
    Tier,
    User,
)
from core.tests.helpers import create_customer_booking

MAINTENANCE = {"kind": BookingKind.MAINTENANCE, "reason": "Net repair"}


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
    booking = create_customer_booking(court, user, "2024-06-01T10:00:00Z")
    assert booking.id is not None
    assert Booking.objects.count() == 1
    assert booking.order.bookings.get() == booking
    assert booking.price_charged == Decimal("50.00")


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
    create_customer_booking(court, user, "2024-06-01T10:00:00Z")
    with (
        pytest.raises(IntegrityError, match="unique_booking_per_court_time"),
        transaction.atomic(),
    ):
        create_customer_booking(court, user, "2024-06-01T10:00:00Z")


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
    booking1 = create_customer_booking(court, user, "2024-06-01T10:00:00Z")
    booking1.status = BookingStatus.CANCELLED
    booking1.save()

    booking2 = create_customer_booking(court, user, "2024-06-01T10:00:00Z")
    assert booking2.id is not None
    assert Booking.objects.count() == 2


@pytest.mark.django_db
def test_rejects_duplicate_active_slot_with_400():
    client = APIClient()
    user = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
    }
    response1 = client.post("/api/v1/bookings/", booking_data)
    assert response1.status_code == 201
    response2 = client.post("/api/v1/bookings/", booking_data)
    assert response2.status_code == 400


@pytest.mark.django_db
def test_accepts_slot_reuse_after_cancellation_with_201():
    client = APIClient()
    user = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
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
        create_customer_booking(
            court, user, "2024-06-01T10:30:00Z", ends_at="2024-06-01T11:30:00Z"
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
        create_customer_booking(
            court, user, "2024-06-01T10:00:00.123Z", ends_at="2024-06-01T11:00:00.123Z"
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
        create_customer_booking(
            court, user, "2024-06-01T10:00:00Z", ends_at="2024-06-01T12:00:00Z"
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
    booking1 = create_customer_booking(court, user, "2024-06-01T10:00:00Z")
    booking2 = create_customer_booking(court, user, "2024-06-01T11:00:00Z")
    assert booking1.id is not None
    assert booking2.id is not None
    assert Booking.objects.count() == 2


@pytest.mark.django_db
def test_derives_ends_at_one_hour_after_starts_with_201():
    client = APIClient()
    user = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.ends_at == datetime(2024, 6, 1, 12, 0, tzinfo=UTC)


@pytest.mark.django_db
def test_rejects_booking_off_the_hour_with_400():
    client = APIClient()
    user = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:30:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 400
    assert "starts_at" in response.data


@pytest.mark.django_db
def test_rejects_booking_with_fractional_seconds_with_400():
    client = APIClient()
    user = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00.123Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 400
    assert "starts_at" in response.data


@pytest.mark.django_db
def test_ignores_client_ends_at_with_201():
    client = APIClient()
    user = User.objects.create_user(
        username="staff", password="testpass", role=Role.STAFF
    )
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    client.force_authenticate(user=user)
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
        "ends_at": "2024-06-01T14:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.ends_at == datetime(2024, 6, 1, 12, 0, tzinfo=UTC)


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
        create_customer_booking(court, user, "2024-06-01T10:00:00Z", status="PENDING")


@pytest.mark.django_db
def test_accepts_maintenance_without_user_at_database_level():
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
        kind=BookingKind.MAINTENANCE,
        reason="Net repair",
    )
    assert Booking.objects.get(id=booking.id).user is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind, has_user, has_order, has_price, reason",
    [
        (BookingKind.CUSTOMER, False, True, True, ""),
        (BookingKind.CUSTOMER, True, False, True, ""),
        (BookingKind.CUSTOMER, True, True, False, ""),
        (BookingKind.CUSTOMER, True, True, True, "Net repair"),
        (BookingKind.MAINTENANCE, True, False, False, "Net repair"),
        (BookingKind.MAINTENANCE, False, True, False, "Net repair"),
        (BookingKind.MAINTENANCE, False, False, True, "Net repair"),
        (BookingKind.MAINTENANCE, False, False, False, ""),
        ("EVENT", True, True, True, ""),
    ],
)
def test_rejects_kind_mismatching_fields_at_database_level(
    kind, has_user, has_order, has_price, reason
):
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    order = Order.objects.create(user=user, created_by=user)
    with (
        pytest.raises(IntegrityError, match="booking_kind_fields_consistent"),
        transaction.atomic(),
    ):
        Booking.objects.create(
            court=court,
            starts_at="2024-06-01T10:00:00Z",
            ends_at="2024-06-01T11:00:00Z",
            user=user if has_user else None,
            order=order if has_order else None,
            price_charged=Decimal("50.00") if has_price else None,
            created_by=user,
            kind=kind,
            reason=reason,
        )


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
    booking = create_customer_booking(
        court, customer, "2024-06-01T10:00:00Z", created_by=staff
    )
    assert Booking.objects.get(id=booking.id).user == customer
    assert customer.bookings.count() == 1
    assert staff.bookings.count() == 0
    assert staff.created_bookings.count() == 1


@pytest.mark.django_db
def test_accepts_order_with_pending_default_at_database_level():
    staff = User.objects.create_user(
        username="staffuser", password="testpass", role=Role.STAFF
    )
    customer = User.objects.create_user(
        username="customeruser", password="testpass", role=Role.CUSTOMER
    )
    order = Order.objects.create(user=customer, created_by=staff)
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING
    assert order.created_at is not None
    assert order.user == customer
    assert order.created_by == staff


@pytest.mark.django_db
def test_rejects_invalid_order_status_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    with (
        pytest.raises(IntegrityError, match="order_status_valid"),
        transaction.atomic(),
    ):
        Order.objects.create(user=user, created_by=user, status="REFUNDED")


@pytest.mark.django_db
def test_rejects_deleting_order_with_bookings_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpass")
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    booking = create_customer_booking(court, user, "2024-06-01T10:00:00Z")
    with pytest.raises(ProtectedError):
        booking.order.delete()
    assert Booking.objects.filter(id=booking.id).exists()


@pytest.mark.django_db
def test_rejects_anonymous_booking_list_with_401():
    client = APIClient()
    response = client.get("/api/v1/bookings/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_rejects_anonymous_booking_creation_with_401():
    client = APIClient()
    court = Court.objects.create(
        name="Court 1",
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=True,
    )
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 401
    assert Booking.objects.count() == 0


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
    booking1 = create_customer_booking(court, customer1, "2024-06-01T11:00:00Z")
    create_customer_booking(court, customer2, "2024-06-01T12:00:00Z")
    client.force_authenticate(user=customer1)
    response = client.get("/api/v1/bookings/")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == booking1.id
    assert response.data[0]["order"] == booking1.order.id
    assert response.data[0]["price_charged"] == "50.00"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra_data",
    [{}, MAINTENANCE],
)
def test_rejects_booking_creation_for_customer_with_403(extra_data):
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
    booking_data = {"court": court.id, "starts_at": "2024-06-01T11:00:00Z"}
    response = client.post("/api/v1/bookings/", booking_data | extra_data)
    assert response.status_code == 403
    assert Booking.objects.count() == 0


@pytest.mark.django_db
def test_accepts_maintenance_for_staff_with_201():
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
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.user is None
    assert booking.order is None
    assert booking.price_charged is None
    assert booking.kind == BookingKind.MAINTENANCE
    assert booking.reason == "Net repair"
    assert booking.created_by == staff


@pytest.mark.django_db
@pytest.mark.parametrize(
    "extra_data, with_user, error_field",
    [
        ({}, False, "kind"),
        ({}, True, "kind"),
        ({"kind": BookingKind.CUSTOMER}, True, "kind"),
        ({"reason": "Net repair"}, False, "kind"),
        ({"kind": BookingKind.MAINTENANCE}, False, "reason"),
        ({"kind": BookingKind.MAINTENANCE, "reason": "   "}, False, "reason"),
        (MAINTENANCE, True, "user"),
    ],
)
def test_rejects_non_maintenance_fields_for_staff_with_400(
    extra_data, with_user, error_field
):
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
    booking_data = {"court": court.id, "starts_at": "2024-06-01T11:00:00Z"}
    if with_user:
        booking_data["user"] = customer.id
    response = client.post("/api/v1/bookings/", booking_data | extra_data)
    assert response.status_code == 400
    assert error_field in response.data
    assert Booking.objects.count() == 0


@pytest.mark.django_db
def test_ignores_order_and_price_in_body_for_staff_with_201():
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
    order = Order.objects.create(user=staff, created_by=staff)
    client.force_authenticate(user=staff)
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
        "order": order.id,
        "price_charged": "10.00",
    }
    response = client.post("/api/v1/bookings/", booking_data)
    assert response.status_code == 201
    booking = Booking.objects.get(id=response.data["id"])
    assert booking.order is None
    assert booking.price_charged is None


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
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
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
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
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
    booking_data = MAINTENANCE | {
        "court": court.id,
        "starts_at": "2024-06-01T11:00:00Z",
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
    assert booking.starts_at == datetime(2024, 6, 1, 11, tzinfo=UTC)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "starts_at, expected_status",
    [
        ("2026-10-01T07:00:00-03:00", 400),
        ("2026-10-01T08:00:00-03:00", 201),
        ("2026-10-01T21:00:00-03:00", 201),
        ("2026-10-01T22:00:00-03:00", 400),
        ("2026-10-01T10:00:00Z", 400),
        ("2026-10-01T11:00:00Z", 201),
    ],
)
def test_validates_working_hours_boundaries(starts_at, expected_status):
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
    response = client.post(
        "/api/v1/bookings/",
        MAINTENANCE | {"court": court.id, "starts_at": starts_at},
    )
    assert response.status_code == expected_status
    if expected_status == 400:
        assert "starts_at" in response.data
