from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse

from portal.models import Event, month_range

KL = ZoneInfo("Asia/Kuala_Lumpur")


def at(year, month, day, hour=9, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=KL)


@pytest.fixture
def event(db):
    def _make(title, start, end=None, **fields):
        return Event.objects.create(title=title, starts_at=start, ends_at=end, **fields)

    return _make


def test_new_events_are_plain_events(event):
    assert event("Assembly", at(2026, 10, 5)).kind == Event.EVENT


def test_month_range_is_local_midnight():
    start, end = month_range(date(2026, 12, 1))
    assert start == datetime(2026, 12, 1, tzinfo=KL)
    assert end == datetime(2027, 1, 1, tzinfo=KL)


def test_overlapping_finds_events_that_touch_the_month(event):
    event("In October", at(2026, 10, 5))
    event("Just after midnight on the 1st", at(2026, 10, 1, 0, 30))
    event("Holiday across months", at(2026, 9, 28), at(2026, 10, 2), all_day=True)
    event("December holiday", at(2026, 12, 21), at(2027, 1, 1), all_day=True)
    event("September", at(2026, 9, 10))

    october = {e.title for e in Event.objects.overlapping(*month_range(date(2026, 10, 1)))}
    january = {e.title for e in Event.objects.overlapping(*month_range(date(2027, 1, 1)))}

    assert october == {"In October", "Just after midnight on the 1st", "Holiday across months"}
    assert january == {"December holiday"}


def test_admin_lists_and_filters_by_type(event, admin_client):
    event("Cuti Deepavali", at(2026, 10, 20), kind=Event.HOLIDAY)
    event("Assembly", at(2026, 10, 5))

    url = reverse("admin:portal_event_changelist") + "?kind__exact=holiday"
    html = admin_client.get(url).content.decode()

    assert "Cuti Deepavali" in html
    assert "Assembly" not in html
