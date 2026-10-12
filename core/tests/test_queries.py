from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from core.models import Court, Order, Role, Sport, Tier, User
from core.tests.helpers import create_customer_booking

# Each list must run a fixed number of queries, whatever the number of rows.
# The same count for 1 and for 5 rows is what proves there is no N+1.
# Every paginated list adds one COUNT query for the "count" field.
ROWS = [1, 5]


def create_court(name):
    return Court.objects.create(
        name=name,
        sports=[Sport.VOLLEYBALL],
        tier=Tier.BASIC,
        hour_price=Decimal("50.00"),
    )


def create_orders(customer, count, bookings_per_order=2):
    court = create_court("Court 1")
    for order_index in range(count):
        order = Order.objects.create(user=customer, created_by=customer)
        for booking_index in range(bookings_per_order):
            hour = 8 + order_index * bookings_per_order + booking_index
            create_customer_booking(
                court, customer, f"2030-10-01T{hour:02d}:00:00-03:00", order=order
            )


@pytest.mark.django_db
@pytest.mark.parametrize("rows", ROWS)
@pytest.mark.parametrize("role", [Role.CUSTOMER, Role.STAFF])
def test_lists_orders_with_their_bookings_and_total_in_three_queries(
    django_assert_num_queries, rows, role
):
    # The count, the orders with the annotated total, and their bookings.
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    create_orders(customer, rows)
    requester = (
        customer
        if role == Role.CUSTOMER
        else User.objects.create_user(username="staff", role=Role.STAFF)
    )
    client = APIClient()
    client.force_authenticate(user=requester)
    with django_assert_num_queries(3):
        response = client.get("/api/v1/orders/")
    assert response.status_code == 200
    assert response.data["count"] == rows


@pytest.mark.django_db
@pytest.mark.parametrize("rows", ROWS)
@pytest.mark.parametrize("role", [Role.CUSTOMER, Role.STAFF])
def test_lists_bookings_in_two_queries(django_assert_num_queries, rows, role):
    # The owner is read through the order: it must come in the same query.
    customer = User.objects.create_user(username="customer", role=Role.CUSTOMER)
    create_orders(customer, rows, bookings_per_order=1)
    requester = (
        customer
        if role == Role.CUSTOMER
        else User.objects.create_user(username="staff", role=Role.STAFF)
    )
    client = APIClient()
    client.force_authenticate(user=requester)
    with django_assert_num_queries(2):
        response = client.get("/api/v1/bookings/")
    assert response.status_code == 200
    assert response.data["count"] == rows
    assert all(booking["user"] == customer.id for booking in response.data["results"])


@pytest.mark.django_db
@pytest.mark.parametrize("rows", ROWS)
def test_lists_courts_in_two_queries(django_assert_num_queries, rows):
    for index in range(rows):
        create_court(f"Court {index}")
    with django_assert_num_queries(2):
        response = APIClient().get("/api/v1/courts/")
    assert response.status_code == 200
    assert response.data["count"] == rows
