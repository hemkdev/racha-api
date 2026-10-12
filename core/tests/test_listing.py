from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from core.models import (
    Court,
    Order,
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


# Search


@pytest.mark.django_db
def test_searches_courts_by_name():
    create_court("Sand Arena")
    create_court("Indoor Hall")
    response = APIClient().get("/api/v1/courts/?search=sand")
    assert [court["name"] for court in results(response)] == ["Sand Arena"]
