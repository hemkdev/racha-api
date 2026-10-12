from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from core.models import Court, Role, Sport, Tier, User
from core.tests.helpers import create_customer_booking


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
