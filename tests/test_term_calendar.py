from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django.utils import timezone

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


def events_page(client, query=""):
    return client.get(reverse("portal:event_list") + query)


def test_page_opens_on_this_month(client, db):
    assert events_page(client).context["month"] == timezone.localdate().replace(day=1)


@pytest.mark.parametrize("query", ["?month=2026-13", "?month=junk", "?show=past", "?month=1999-01"])
def test_bad_or_old_links_show_this_month(client, db, query):
    assert events_page(client, query).context["month"] == timezone.localdate().replace(day=1)


def test_month_shows_events_spanning_into_it(event, client):
    event("December holiday", at(2026, 12, 21), at(2027, 1, 1), all_day=True, kind=Event.HOLIDAY)
    event("Exam week", at(2027, 1, 11), at(2027, 1, 15), all_day=True, kind=Event.EXAM)

    response = events_page(client, "?month=2027-01")

    assert [e.title for e in response.context["events"]] == ["December holiday", "Exam week"]
    html = response.content.decode()
    assert "January 2027" in html
    assert 'href="?month=2026-12"' in html
    assert 'href="?month=2027-02"' in html


def test_filter_shows_one_type_and_is_kept_between_months(event, client):
    event("Cuti", at(2026, 10, 20), all_day=True, kind=Event.HOLIDAY)
    event("Assembly", at(2026, 10, 5))

    response = events_page(client, "?month=2026-10&type=holiday")

    assert [e.title for e in response.context["events"]] == ["Cuti"]
    html = response.content.decode()
    assert 'href="?month=2026-11&amp;type=holiday"' in html
    assert 'aria-current="page">Holidays</a>' in html


def test_unknown_type_shows_everything(event, client):
    event("Assembly", at(2026, 10, 5))
    assert len(events_page(client, "?month=2026-10&type=nonsense").context["events"]) == 1


def test_empty_month_points_to_the_next_month_with_events(event, client):
    event("Exam week", at(2026, 12, 7), kind=Event.EXAM)

    html = events_page(client, "?month=2026-10").content.decode()
    assert "No events this month." in html
    assert '<a href="?month=2026-12">Next: December 2026</a>' in html

    html = events_page(client, "?month=2026-10&type=holiday").content.decode()
    assert "No events this month." in html
    assert "Next: " not in html


def test_type_labels_and_holiday_band(event, client):
    event("Cuti Deepavali", at(2026, 10, 20), all_day=True, kind=Event.HOLIDAY)
    event("UPSA", at(2026, 10, 12), kind=Event.EXAM)
    event("Assembly", at(2026, 10, 5))

    html = events_page(client, "?month=2026-10").content.decode()

    assert "event-row--holiday" in html
    assert '<p class="kind kind--exam">Exam</p>' in html
    assert html.count('<p class="kind') == 2


def test_drafts_stay_off_the_calendar(event, client):
    event("Draft trip", at(2026, 10, 5), is_published=False)
    assert events_page(client, "?month=2026-10").context["events"] == []
