from datetime import datetime
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from core.models import (
    Booking,
    BookingKind,
    Court,
    Order,
    OrderStatus,
    Role,
    Sport,
    Tier,
    User,
)
from core.tests.helpers import create_customer_booking, freeze_now


def create_court(name, sports=(Sport.VOLLEYBALL,), **extra):
    fields = {
        "name": name,
        "sports": list(sports),
        "tier": Tier.BASIC,
        "hour_price": Decimal("50.00"),
    } | extra
    return Court.objects.create(**fields)


def staff_client():
    staff = User.objects.create_user(username="staff", role=Role.STAFF)
    client = APIClient()
    client.force_authenticate(user=staff)
    return client, staff


def results(response):
    assert response.status_code == 200, response.data
    return response.data["results"]


# Pagination


@pytest.mark.django_db
def test_paginates_lists_in_pages_of_twenty():
    for index in range(25):
        create_court(f"Court {index:02d}")
    client = APIClient()
    first = client.get("/api/v1/courts/")
    assert first.status_code == 200
    assert first.data["count"] == 25
    assert len(first.data["results"]) == 20
    assert first.data["previous"] is None
    assert first.data["next"] is not None
    second = client.get("/api/v1/courts/?page=2")
    assert len(second.data["results"]) == 5
    assert second.data["previous"] is not None
    assert second.data["next"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/api/v1/bookings/", "/api/v1/orders/"])
def test_paginates_bookings_and_orders(path):
    client, _ = staff_client()
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    court = create_court("Court 1")
    for day in range(1, 22):
        create_customer_booking(court, customer, f"2030-10-{day:02d}T08:00:00-03:00")
    response = client.get(path)
    assert response.data["count"] == 21
    assert len(response.data["results"]) == 20


@pytest.mark.django_db
def test_rejects_page_out_of_range_with_404():
    create_court("Court 1")
    response = APIClient().get("/api/v1/courts/?page=2")
    assert response.status_code == 404


# Ordering


@pytest.mark.django_db
def test_orders_courts_by_name_by_default():
    for name in ["Bravo", "Alpha", "Charlie"]:
        create_court(name)
    names = [court["name"] for court in results(APIClient().get("/api/v1/courts/"))]
    assert names == ["Alpha", "Bravo", "Charlie"]


@pytest.mark.django_db
def test_orders_courts_by_requested_field():
    create_court("Alpha", hour_price=Decimal("50.00"))
    create_court("Bravo", hour_price=Decimal("80.00"))
    create_court("Charlie", hour_price=Decimal("60.00"))
    response = APIClient().get("/api/v1/courts/?ordering=-hour_price")
    names = [court["name"] for court in results(response)]
    assert names == ["Bravo", "Charlie", "Alpha"]


@pytest.mark.django_db
def test_ignores_ordering_by_field_not_allowed():
    for name in ["Bravo", "Alpha"]:
        create_court(name)
    response = APIClient().get("/api/v1/courts/?ordering=-id")
    names = [court["name"] for court in results(response)]
    assert names == ["Alpha", "Bravo"]


@pytest.mark.django_db
def test_orders_bookings_by_start_by_default():
    client, _ = staff_client()
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    court = create_court("Court 1")
    for hour in [10, 8, 9]:
        create_customer_booking(court, customer, f"2030-10-01T{hour:02d}:00:00-03:00")
    hours = [b["starts_at"][11:13] for b in results(client.get("/api/v1/bookings/"))]
    assert hours == ["08", "09", "10"]


@pytest.mark.django_db
def test_orders_orders_newest_first_by_default():
    client, _ = staff_client()
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    created = []
    for minute in [0, 2, 1]:
        with freeze_now(f"2030-09-01T10:{minute:02d}:00"):
            created.append(Order.objects.create(user=customer, created_by=customer))
    ids = [order["id"] for order in results(client.get("/api/v1/orders/"))]
    assert ids == [created[1].id, created[2].id, created[0].id]


@pytest.mark.django_db
def test_orders_orders_by_total():
    client, _ = staff_client()
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    court = create_court("Court 1")
    expensive = Order.objects.create(user=customer, created_by=customer)
    cheap = Order.objects.create(user=customer, created_by=customer)
    for hour in [8, 9]:
        create_customer_booking(
            court, customer, f"2030-10-01T{hour:02d}:00:00-03:00", order=expensive
        )
    create_customer_booking(court, customer, "2030-10-01T10:00:00-03:00", order=cheap)
    response = client.get("/api/v1/orders/?ordering=total")
    assert [order["id"] for order in results(response)] == [cheap.id, expensive.id]


# Filters


@pytest.mark.django_db
def test_filters_courts_by_one_of_their_sports():
    sand = create_court("Sand", sports=[Sport.BEACH_TENNIS, Sport.FOOTVOLLEY])
    create_court("Indoor", sports=[Sport.FUTSAL])
    response = APIClient().get("/api/v1/courts/?sport=FOOTVOLLEY")
    assert [court["id"] for court in results(response)] == [sand.id]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query, expected",
    [("tier=PREMIUM", ["Premium"]), ("is_active=false", ["Closed"])],
)
def test_filters_courts_by_tier_and_activity(query, expected):
    create_court("Basic")
    create_court("Premium", tier=Tier.PREMIUM)
    create_court("Closed", is_active=False)
    response = APIClient().get(f"/api/v1/courts/?{query}")
    assert [court["name"] for court in results(response)] == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path, param",
    [
        ("/api/v1/courts/?sport=CURLING", "sport"),
        ("/api/v1/courts/?tier=GOLD", "tier"),
        ("/api/v1/courts/?is_active=maybe", "is_active"),
        ("/api/v1/bookings/?from=yesterday", "from"),
        ("/api/v1/bookings/?from=2030-10-02&to=2030-10-01", "to"),
        ("/api/v1/orders/?status=REFUNDED", "status"),
        ("/api/v1/orders/?to=2030-13-01", "to"),
    ],
)
def test_rejects_invalid_filter_with_400(path, param):
    client, _ = staff_client()
    response = client.get(path)
    assert response.status_code == 400
    assert param in response.data


@pytest.mark.django_db
def test_filters_bookings_by_local_day_period():
    client, staff = staff_client()
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    court = create_court("Court 1")
    create_customer_booking(court, customer, "2030-09-30T21:00:00-03:00")
    first = create_customer_booking(court, customer, "2030-10-01T08:00:00-03:00")
    # 21:00 local on October 1st is already October 2nd in UTC.
    last = create_customer_booking(court, customer, "2030-10-01T21:00:00-03:00")
    maintenance = Booking.objects.create(
        court=court,
        starts_at=datetime.fromisoformat("2030-10-01T12:00:00-03:00"),
        ends_at=datetime.fromisoformat("2030-10-01T13:00:00-03:00"),
        created_by=staff,
        kind=BookingKind.MAINTENANCE,
        reason="Net repair",
    )
    create_customer_booking(court, customer, "2030-10-02T08:00:00-03:00")
    response = client.get("/api/v1/bookings/?from=2030-10-01&to=2030-10-01")
    assert [b["id"] for b in results(response)] == [first.id, maintenance.id, last.id]


@pytest.mark.django_db
def test_filters_orders_by_status_and_creation_period():
    client, _ = staff_client()
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    with freeze_now("2030-09-30T23:30:00"):
        Order.objects.create(user=customer, created_by=customer)
    with freeze_now("2030-10-01T10:00:00"):
        pending = Order.objects.create(user=customer, created_by=customer)
        Order.objects.create(
            user=customer, created_by=customer, status=OrderStatus.PAID
        )
    response = client.get("/api/v1/orders/?status=PENDING&from=2030-10-01")
    assert [order["id"] for order in results(response)] == [pending.id]


@pytest.mark.django_db
def test_counts_only_filtered_rows():
    for index in range(3):
        create_court(f"Futsal {index}", sports=[Sport.FUTSAL])
    create_court("Volleyball")
    response = APIClient().get("/api/v1/courts/?sport=FUTSAL")
    assert response.data["count"] == 3


# Search


@pytest.mark.django_db
def test_searches_courts_by_name():
    create_court("Sand Arena")
    create_court("Indoor Hall")
    response = APIClient().get("/api/v1/courts/?search=sand")
    assert [court["name"] for court in results(response)] == ["Sand Arena"]
