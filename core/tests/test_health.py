from unittest import mock

import pytest
from django.db import DatabaseError
from django.test import Client


@pytest.mark.django_db
def test_reports_ok_when_the_database_answers():
    response = Client().get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_reports_unavailable_when_the_database_fails():
    with mock.patch("core.views.connection.cursor", side_effect=DatabaseError):
        response = Client().get("/health/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.django_db
def test_is_not_throttled():
    client = Client()
    for _ in range(61):
        assert client.get("/health/").status_code == 200
