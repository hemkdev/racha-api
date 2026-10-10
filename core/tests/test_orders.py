from datetime import datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.db import IntegrityError
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

SLOT_TAKEN = "This court is already booked for the selected time slot."


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
    assert errors[1] == {"starts_at": [SLOT_TAKEN]}
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
    assert errors[1] == {"starts_at": [SLOT_TAKEN]}
    assert_nothing_created()


@pytest.mark.django_db
def test_does_not_mask_other_constraint_as_slot_taken():
    # A zero price breaks booking_kind_fields_consistent, not the slot constraint:
    # it must surface as an error, never as a 400 claiming the slot is taken.
    client = APIClient()
    customer = create_user("customer")
    court = create_court()
    client.force_authenticate(user=customer)
    data = {"bookings": [{"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"}]}
    with (
        mock.patch.object(Court, "price_at", return_value=Decimal("0.00")),
        pytest.raises(IntegrityError, match="booking_kind_fields_consistent"),
    ):
        client.post("/api/v1/orders/", data, format="json")
    assert_nothing_created()


def create_order(user, slots, court=None, status=OrderStatus.PENDING):
    court = court or create_court()
    order = Order.objects.create(user=user, created_by=user, status=status)
    for starts_at in slots:
        create_customer_booking(
            court,
            user,
            starts_at,
            order=order,
            price_charged=court.price_at(datetime.fromisoformat(starts_at)),
        )
    return order


@pytest.mark.django_db
def test_returns_total_in_creation_response_with_201():
    client = APIClient()
    customer = create_user("customer")
    court = create_court()
    client.force_authenticate(user=customer)
    data = {
        "bookings": [
            {"court": court.id, "starts_at": "2026-10-01T08:00:00-03:00"},
            {"court": court.id, "starts_at": "2026-10-01T18:00:00-03:00"},
        ]
    }
    response = client.post("/api/v1/orders/", data, format="json")
    assert response.status_code == 201
    assert response.data["total"] == "125.00"


@pytest.mark.django_db
def test_lists_only_own_orders_with_total_for_customer_with_200():
    client = APIClient()
    customer = create_user("customer")
    other = create_user("other")
    court = create_court()
    order = create_order(
        customer,
        ["2026-10-01T08:00:00-03:00", "2026-10-01T18:00:00-03:00"],
        court=court,
    )
    create_order(other, ["2026-10-01T09:00:00-03:00"], court=court)
    client.force_authenticate(user=customer)
    response = client.get("/api/v1/orders/")
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == order.id
    assert response.data[0]["total"] == "125.00"
    assert len(response.data[0]["bookings"]) == 2


@pytest.mark.django_db
def test_lists_every_order_for_staff_with_200():
    client = APIClient()
    staff = create_user("staff", role=Role.STAFF)
    court = create_court()
    create_order(create_user("customer1"), ["2026-10-01T08:00:00-03:00"], court=court)
    create_order(create_user("customer2"), ["2026-10-01T09:00:00-03:00"], court=court)
    client.force_authenticate(user=staff)
    response = client.get("/api/v1/orders/")
    assert response.status_code == 200
    assert len(response.data) == 2


@pytest.mark.django_db
def test_rejects_anonymous_order_list_with_401():
    response = APIClient().get("/api/v1/orders/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_retrieves_own_order_with_total_with_200():
    client = APIClient()
    customer = create_user("customer")
    order = create_order(customer, ["2026-10-01T08:00:00-03:00"])
    client.force_authenticate(user=customer)
    response = client.get(f"/api/v1/orders/{order.id}/")
    assert response.status_code == 200
    assert response.data["total"] == "50.00"
    assert response.data["status"] == OrderStatus.PENDING


@pytest.mark.django_db
def test_hides_order_of_another_customer_with_404():
    client = APIClient()
    customer = create_user("customer")
    order = create_order(create_user("other"), ["2026-10-01T08:00:00-03:00"])
    client.force_authenticate(user=customer)
    response = client.get(f"/api/v1/orders/{order.id}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_excludes_cancelled_bookings_from_total():
    client = APIClient()
    customer = create_user("customer")
    order = create_order(
        customer, ["2026-10-01T08:00:00-03:00", "2026-10-01T18:00:00-03:00"]
    )
    peak = datetime.fromisoformat("2026-10-01T18:00:00-03:00")
    order.bookings.filter(starts_at=peak).update(status=BookingStatus.CANCELLED)
    client.force_authenticate(user=customer)
    response = client.get(f"/api/v1/orders/{order.id}/")
    assert response.data["total"] == "50.00"


@pytest.mark.django_db
def test_returns_zero_total_when_every_booking_is_cancelled():
    client = APIClient()
    customer = create_user("customer")
    order = create_order(customer, ["2026-10-01T08:00:00-03:00"])
    order.bookings.update(status=BookingStatus.CANCELLED)
    client.force_authenticate(user=customer)
    response = client.get(f"/api/v1/orders/{order.id}/")
    assert response.data["total"] == "0.00"


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_rejects_order_update_and_delete_with_405(method):
    client = APIClient()
    staff = create_user("staff", role=Role.STAFF)
    order = create_order(create_user("customer"), ["2026-10-01T08:00:00-03:00"])
    client.force_authenticate(user=staff)
    response = getattr(client, method)(f"/api/v1/orders/{order.id}/", {}, format="json")
    assert response.status_code == 405


@pytest.mark.django_db
def test_confirms_pending_order_for_staff_with_200():
    client = APIClient()
    staff = create_user("staff", role=Role.STAFF)
    order = create_order(create_user("customer"), ["2026-10-01T08:00:00-03:00"])
    client.force_authenticate(user=staff)
    response = client.post(f"/api/v1/orders/{order.id}/confirm/")
    assert response.status_code == 200
    assert response.data["status"] == OrderStatus.PAID
    order.refresh_from_db()
    assert order.status == OrderStatus.PAID


@pytest.mark.django_db
def test_rejects_confirm_by_customer_with_403():
    client = APIClient()
    customer = create_user("customer")
    order = create_order(customer, ["2026-10-01T08:00:00-03:00"])
    client.force_authenticate(user=customer)
    response = client.post(f"/api/v1/orders/{order.id}/confirm/")
    assert response.status_code == 403
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING


@pytest.mark.django_db
@pytest.mark.parametrize("status", [OrderStatus.PAID, OrderStatus.CANCELLED])
def test_rejects_confirm_of_non_pending_order_with_409(status):
    client = APIClient()
    staff = create_user("staff", role=Role.STAFF)
    order = create_order(
        create_user("customer"), ["2026-10-01T08:00:00-03:00"], status=status
    )
    client.force_authenticate(user=staff)
    response = client.post(f"/api/v1/orders/{order.id}/confirm/")
    assert response.status_code == 409
    order.refresh_from_db()
    assert order.status == status


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.CUSTOMER, Role.STAFF])
def test_cancels_pending_order_and_its_bookings_with_200(role):
    client = APIClient()
    customer = create_user("customer")
    order = create_order(
        customer, ["2026-10-01T08:00:00-03:00", "2026-10-01T09:00:00-03:00"]
    )
    requester = customer if role == Role.CUSTOMER else create_user("staff", role=role)
    client.force_authenticate(user=requester)
    response = client.post(f"/api/v1/orders/{order.id}/cancel/")
    assert response.status_code == 200
    assert response.data["status"] == OrderStatus.CANCELLED
    assert response.data["total"] == "0.00"
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    assert not order.bookings.filter(status=BookingStatus.ACTIVE).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status", [OrderStatus.PAID, OrderStatus.CANCELLED])
def test_rejects_cancel_of_non_pending_order_with_409(status):
    client = APIClient()
    customer = create_user("customer")
    order = create_order(customer, ["2026-10-01T08:00:00-03:00"], status=status)
    client.force_authenticate(user=customer)
    response = client.post(f"/api/v1/orders/{order.id}/cancel/")
    assert response.status_code == 409
    order.refresh_from_db()
    assert order.status == status
    assert order.bookings.filter(status=BookingStatus.ACTIVE).exists()


@pytest.mark.django_db
def test_rejects_cancel_of_another_customers_order_with_404():
    client = APIClient()
    order = create_order(create_user("other"), ["2026-10-01T08:00:00-03:00"])
    client.force_authenticate(user=create_user("customer"))
    response = client.post(f"/api/v1/orders/{order.id}/cancel/")
    assert response.status_code == 404
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING
