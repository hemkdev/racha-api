import threading
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from django.db import connection
from rest_framework.test import APIClient

from core.models import Booking, Order


def create_customer_booking(court, user, starts_at, created_by=None, **extra):
    created_by = created_by or user
    if isinstance(starts_at, str):
        starts_at = datetime.fromisoformat(starts_at)
    fields = {
        "court": court,
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


def post_concurrently(requests, *models):
    # Each thread stops at a barrier right after its first save of any of the given
    # models, so both have passed their checks and written before either goes on.
    # Once a row lock serializes the requests, the second one blocks before saving,
    # the barrier never fills, and the timeout lets the lock holder finish.
    barrier = threading.Barrier(len(requests), timeout=2)
    waited = set()
    responses = [None] * len(requests)

    def stop_after_first_save(original):
        def save(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            if threading.get_ident() not in waited:
                waited.add(threading.get_ident())
                try:
                    barrier.wait()
                except threading.BrokenBarrierError:
                    pass
            return result

        return save

    def post(index, user, path):
        client = APIClient()
        client.force_authenticate(user=user)
        try:
            responses[index] = client.post(path)
        except Exception as error:
            responses[index] = error
        finally:
            connection.close()

    with ExitStack() as stack:
        for model in models:
            patched = stop_after_first_save(model.save)
            stack.enter_context(mock.patch.object(model, "save", patched))
        threads = [
            threading.Thread(target=post, args=(index, *request))
            for index, request in enumerate(requests)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    for response in responses:
        assert not isinstance(response, Exception), repr(response)
    return responses
