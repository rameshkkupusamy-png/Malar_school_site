from datetime import timedelta

import pytest
from django.utils import timezone

from portal.models import Event


@pytest.fixture
def make_event(db):
    def _make(title="Sports day", days=7, **fields):
        return Event.objects.create(
            title=title, starts_at=timezone.now() + timedelta(days=days), **fields
        )

    return _make
