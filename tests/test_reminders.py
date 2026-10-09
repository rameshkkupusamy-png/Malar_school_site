"""The evening before, subscribers get one email listing tomorrow's events."""

from datetime import datetime, time, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from portal.models import Event, Subscriber
from portal.notifications import send_reminders


def day(offset: int, hour: int = 9) -> datetime:
    """Local time on today + offset days."""
    return timezone.make_aware(
        datetime.combine(timezone.localdate() + timedelta(days=offset), time(hour))
    )


@pytest.fixture
def event(db):
    def _make(title, starts_at, **fields):
        return Event.objects.create(title=title, starts_at=starts_at, **fields)

    return _make


@pytest.fixture
def parents(db):
    return [
        Subscriber.objects.create(email="asha@example.com", name="Asha"),
        Subscriber.objects.create(email="siti@example.com", language="ms"),
        Subscriber.objects.create(email="gone@example.com", is_active=False),
    ]


def test_one_email_per_parent_listing_tomorrows_events(event, parents, mailoutbox, settings):
    settings.SITE_URL = "https://school.example"
    sports = event("Sports day", day(1, 8), location="School field")
    event("Book fair", day(1, 14))
    event("Today's assembly", day(0))
    event("Next week's trip", day(7))
    event("Draft trip", day(1), is_published=False)

    sent = send_reminders()

    assert sent == 2
    assert sorted(m.to[0] for m in mailoutbox) == ["asha@example.com", "siti@example.com"]
    english = next(m for m in mailoutbox if m.to == ["asha@example.com"])
    assert english.body.index("Sports day") < english.body.index("Book fair")
    assert "School field" in english.body
    assert f"https://school.example/events/{sports.pk}/" in english.body
    assert "Today's assembly" not in english.body
    assert "Next week's trip" not in english.body
    assert "Draft trip" not in english.body
    assert "/unsubscribe/" in english.body


def test_each_parent_gets_their_own_language(event, parents, mailoutbox):
    event("Sports day", day(1), title_ms="Hari Sukan")

    send_reminders()

    malay = next(m for m in mailoutbox if m.to == ["siti@example.com"])
    assert "Esok" in malay.subject
    assert "Hari Sukan" in malay.body


def test_multi_day_holiday_is_reminded_the_day_before_it_starts(event, parents, mailoutbox):
    event("Deepavali holiday", day(1), ends_at=day(3), all_day=True, kind=Event.HOLIDAY)
    event("Exam week", day(-1), ends_at=day(2), all_day=True, kind=Event.EXAM)

    send_reminders()

    body = mailoutbox[0].body
    assert "Deepavali holiday" in body
    assert "Exam week" not in body


def test_events_are_reminded_only_once(event, parents, mailoutbox):
    sports = event("Sports day", day(1))

    send_reminders()
    sports.refresh_from_db()
    assert sports.reminded_at is not None

    mailoutbox.clear()
    assert send_reminders() == 0
    assert mailoutbox == []


def test_nothing_is_sent_when_nothing_is_on_tomorrow(event, parents, mailoutbox):
    event("Next week's trip", day(7))
    assert send_reminders() == 0
    assert mailoutbox == []


def test_command_reports_what_it_sent(event, parents, mailoutbox):
    event("Sports day", day(1))
    out = StringIO()

    call_command("send_reminders", stdout=out)

    assert "Sent 2 reminder email(s) about 1 event(s)." in out.getvalue()


@pytest.mark.django_db
def test_sign_up_box_mentions_the_reminder(client):
    html = client.get(reverse("portal:home")).content.decode()
    assert "Get an email when events are added, and a reminder the day before" in html


def test_time_and_place_sit_on_consecutive_lines(event, parents, mailoutbox):
    event("Sports day", day(1, 8), location="School field")
    send_reminders()
    lines = mailoutbox[0].body.splitlines()
    place = lines.index("School field")
    assert lines[place - 1].strip() != ""
