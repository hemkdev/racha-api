import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_throttle_history():
    # Throttles count requests in the cache; without this, one test's requests
    # leak into the next and any of them may get a 429.
    cache.clear()
