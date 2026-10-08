from decimal import Decimal
from unittest import mock

import pytest
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


def create_court(name="Court 1", is_active=True):
    return Court.objects.create(
        name=name,
        sport=Sport.VOLLEYBALL,
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
        is_active=is_active,
    )


def create_user(username, role=Role.CUSTOMER):
    return User.objects.create_user(username=username, password="testpass", role=role)


def assert_nothing_created():
    assert Order.objects.count() == 0
    assert not Booking.objects.filter(kind=BookingKind.CUSTOMER).exists()


@pytest.mark.django_db
def test_creates_order_with_nested_bookings_for_customer_with_201():
    client = APIClient()
    customer = create_user("customer")
    court = create_court()
    client.force_authenticate(user=customer)
    data = {
        "bookings": [
            {"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T09:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T10:00:00-03:00"},
        ]
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 201
    order = Order.objects.get(id=response.data["id"])
    assert order.user == customer
    assert order.created_by == customer
    assert order.status == OrderStatus.PENDING
    assert response.data["status"] == OrderStatus.PENDING
    assert len(response.data["bookings"]) == 3
    bookings = order.bookings.order_by("starts_at")
    assert bookings.count() == 3
    for booking in bookings:
        assert booking.user == customer
        assert booking.created_by == customer
        assert booking.kind == BookingKind.CUSTOMER
        assert booking.status == BookingStatus.ACTIVE
        assert booking.price_charged == Decimal("50.00")


@pytest.mark.django_db
def test_creates_order_for_customer_as_staff_with_201():
    client = APIClient()
    staff = create_user("staff", role=Role.STAFF)
    customer = create_user("customer")
    court = create_court()
    client.force_authenticate(user=staff)
    data = {
        "user": customer.id,
        "bookings": [{"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}],
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 201
    order = Order.objects.get(id=response.data["id"])
    assert order.user == customer
    assert order.created_by == staff
    booking = order.bookings.get()
    assert booking.user == customer
    assert booking.created_by == staff


@pytest.mark.django_db
def test_accepts_slots_from_different_courts_in_one_order_with_201():
    client = APIClient()
    customer = create_user("customer")
    court1 = create_court("Court 1")
    court2 = create_court("Court 2")
    client.force_authenticate(user=customer)
    data = {
        "bookings": [
            {"court": court1.id, "starts_at": "2026-10-01T20:00:00-03:00"},
            {"court": court2.id, "starts_at": "2026-10-01T20:00:00-03:00"},
        ]
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 201
    assert Order.objects.get().bookings.count() == 2


@pytest.mark.django_db
def test_charges_peak_price_by_local_hour_with_201():
    client = APIClient()
    customer = create_user("customer")
    court = create_court()
    client.force_authenticate(user=customer)
    data = {
        "bookings": [
            {"court": court.id, "starts_at": "2026-10-01T17:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T21:00:00Z"},
        ]
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 201
    prices = list(
        Order.objects.get()
        .bookings.order_by("starts_at")
        .values_list("price_charged", flat=True)
    )
    assert prices == [Decimal("50.00"), Decimal("75.00")]
    assert sorted(b["price_charged"] for b in response.data["bookings"]) == [
        "50.00",
        "75.00",
    ]


@pytest.mark.django_db
def test_keeps_price_charged_when_court_price_changes():
    client = APIClient()
    customer = create_user("customer")
    court = create_court()
    client.force_authenticate(user=customer)
    data = {"bookings": [{"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}]}
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 201
    court.hour_price = Decimal("80.00")
    court.save()
    booking = Order.objects.get().bookings.get()
    booking.refresh_from_db()
    assert booking.price_charged == Decimal("50.00")


@pytest.mark.django_db
def test_accepts_slot_of_cancelled_booking_with_201():
    client = APIClient()
    customer = create_user("customer")
    other = create_user("other")
    court = create_court()
    create_customer_booking(
        court, other, "2026-10-01T08:00:00-03:00", status=BookingStatus.CANCELLED
    )
    client.force_authenticate(user=customer)
    data = {"bookings": [{"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}]}
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 201


@pytest.mark.django_db
@pytest.mark.parametrize(
    "blocking_kind", [BookingKind.CUSTOMER, BookingKind.MAINTENANCE]
)
def test_rejects_whole_order_when_one_slot_is_taken_with_400(blocking_kind):
    client = APIClient()
    customer = create_user("customer")
    other = create_user("other")
    staff = create_user("staff", role=Role.STAFF)
    court = create_court()
    if blocking_kind == BookingKind.CUSTOMER:
        create_customer_booking(court, other, "2026-10-01T09:00:00-03:00")
    else:
        Booking.objects.create(
            court=court,
            starts_at="2026-10-01T09:00:00-03:00",
            ends_at="2026-10-01T10:00:00-03:00",
            created_by=staff,
            kind=BookingKind.MAINTENANCE,
            reason="Net repair",
        )
    orders_before = Order.objects.count()
    bookings_before = Booking.objects.count()
    client.force_authenticate(user=customer)
    data = {
        "bookings": [
            {"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T09:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T10:00:00-03:00"},
        ]
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    errors = response.data["bookings"]
    assert set(errors) == {1}
    assert Order.objects.count() == orders_before
    assert Booking.objects.count() == bookings_before


@pytest.mark.django_db
def test_reports_every_failing_slot_with_400():
    client = APIClient()
    customer = create_user("customer")
    other = create_user("other")
    court = create_court()
    inactive = create_court("Court 2", is_active=False)
    create_customer_booking(court, other, "2026-10-01T09:00:00-03:00")
    client.force_authenticate(user=customer)
    data = {
        "bookings": [
            {"court": court.id, "starts_at": "2026-10-01T07:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T09:00:00-03:00"},
            {"court": inactive.id, "starts_at": "2026-10-01T10:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T11:30:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T12:00:00-03:00"},
        ]
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    errors = response.data["bookings"]
    assert set(errors) == {0, 1, 2, 3}
    assert "starts_at" in errors[0]
    assert "court" in errors[2]
    assert "starts_at" in errors[3]
    assert Order.objects.count() == 1
    assert Booking.objects.count() == 1


@pytest.mark.django_db
def test_rejects_unknown_court_with_400():
    client = APIClient()
    customer = create_user("customer")
    client.force_authenticate(user=customer)
    data = {"bookings": [{"court": 999, "starts_at": "2026-10-01T08:00:00-03:00"}]}
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    assert "court" in response.data["bookings"][0]
    assert_nothing_created()


@pytest.mark.django_db
def test_rejects_same_slot_twice_in_one_order_with_400():
    client = APIClient()
    customer = create_user("customer")
    court = create_court()
    client.force_authenticate(user=customer)
    slot = {"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}
    data = {"bookings": [slot, slot]}
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    assert "bookings" in response.data
    assert_nothing_created()


@pytest.mark.django_db
@pytest.mark.parametrize("data", [{}, {"bookings": []}])
def test_rejects_order_without_bookings_with_400(data):
    client = APIClient()
    customer = create_user("customer")
    client.force_authenticate(user=customer)
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    assert "bookings" in response.data
    assert_nothing_created()


@pytest.mark.django_db
def test_rejects_user_in_body_for_customer_with_400():
    client = APIClient()
    customer = create_user("customer")
    other = create_user("other")
    court = create_court()
    client.force_authenticate(user=customer)
    data = {
        "user": other.id,
        "bookings": [{"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}],
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    assert "user" in response.data
    assert_nothing_created()


@pytest.mark.django_db
@pytest.mark.parametrize("target", [None, "self", "other_staff"])
def test_rejects_missing_or_non_customer_user_for_staff_with_400(target):
    client = APIClient()
    staff = create_user("staff", role=Role.STAFF)
    other_staff = create_user("other_staff", role=Role.STAFF)
    court = create_court()
    client.force_authenticate(user=staff)
    data = {"bookings": [{"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}]}
    if target == "self":
        data["user"] = staff.id
    elif target == "other_staff":
        data["user"] = other_staff.id
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    assert "user" in response.data
    assert_nothing_created()


@pytest.mark.django_db
def test_rejects_anonymous_order_with_401():
    client = APIClient()
    court = create_court()
    data = {"bookings": [{"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}]}
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 401
    assert_nothing_created()


@pytest.mark.django_db
def test_rolls_back_order_when_slot_is_taken_during_creation_with_400():
    # Simulates a concurrent request that books slot 1 after validation passed
    # and before this order inserts it: only the database constraint catches it.
    client = APIClient()
    customer = create_user("customer")
    staff = create_user("staff", role=Role.STAFF)
    court = create_court()
    contested = "2026-10-01T09:00:00-03:00"
    original_price_at = Court.price_at

    def price_at_with_race(self, starts_at):
        if not Booking.objects.filter(kind=BookingKind.MAINTENANCE).exists():
            Booking.objects.create(
                court=self,
                starts_at=contested,
                ends_at="2026-10-01T10:00:00-03:00",
                created_by=staff,
                kind=BookingKind.MAINTENANCE,
                reason="Concurrent booking",
            )
        return original_price_at(self, starts_at)

    client.force_authenticate(user=customer)
    data = {
        "bookings": [
            {"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"},
            {"court": court.id, "starts_at": contested},
        ]
    }
    with mock.patch.object(Court, "price_at", autospec=True) as price_at:
        price_at.side_effect = price_at_with_race
        response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 400
    errors = response.data["bookings"]
    assert set(errors) == {1}
    assert_nothing_created()
