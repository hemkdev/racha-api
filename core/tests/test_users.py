import pytest
from django.db import IntegrityError, transaction

from core.models import Role, User


@pytest.mark.django_db
def test_default_role_is_customer_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpassword")

    assert User.objects.get(pk=user.pk).role == Role.CUSTOMER


@pytest.mark.django_db
def test_rejects_invalid_role_at_database_level():
    with pytest.raises(IntegrityError, match="user_role_valid"), transaction.atomic():
        User.objects.create_user(
            username="testuser", password="testpassword", role="INVALID_ROLE"
        )


@pytest.mark.django_db
def test_accepts_valid_role_at_database_level():
    user = User.objects.create_user(
        username="testuser", password="testpassword", role=Role.STAFF
    )

    assert User.objects.get(pk=user.pk).role == Role.STAFF


@pytest.mark.django_db
def test_accepts_user_without_phone_at_database_level():
    user = User.objects.create_user(username="testuser", password="testpassword")

    assert User.objects.get(pk=user.pk).phone == ""
