from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from core.models import Booking, Order


def create_customer_booking(court, user, starts_at, created_by=None, **extra):
    created_by = created_by or user
    if isinstance(starts_at, str):
        starts_at = datetime.fromisoformat(starts_at)
    fields = {
        "court": court,
        "user": user,
        "created_by": created_by,
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(hours=1),
        "price_charged": court.hour_price,
    } | extra
    if "order" not in fields:
        fields["order"] = Order.objects.create(user=user, created_by=created_by)
    return Booking.objects.create(**fields)


def freeze_now(local_iso):
    moment = datetime.fromisoformat(local_iso).replace(
        tzinfo=ZoneInfo("America/Sao_Paulo")
    )
    return mock.patch("django.utils.timezone.now", return_value=moment)
