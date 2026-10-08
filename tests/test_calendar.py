from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.urls import reverse
from django.utils import timezone

from portal.models import Event

KL = ZoneInfo("Asia/Kuala_Lumpur")


def unfold(ics):
    """Join folded lines back together, as calendar apps do."""
    return ics.replace("\r\n ", "")


def get_ics(client, url):
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/calendar")
    return response.content.decode()


@pytest.mark.django_db
def test_event_file_has_title_place_times_and_link(client, settings):
    settings.SITE_URL = "https://school.example"
    event = Event.objects.create(
        title="Sports day",
        location="School field",
        starts_at=datetime(2026, 11, 3, 8, 0, tzinfo=KL),
        ends_at=datetime(2026, 11, 3, 12, 30, tzinfo=KL),
    )

    ics = unfold(get_ics(client, reverse("portal:event_calendar", args=[event.pk])))

    assert ics.startswith("BEGIN:VCALENDAR\r\n")
    assert ics.endswith("END:VCALENDAR\r\n")
    assert "SUMMARY:Sports day\r\n" in ics
    assert "LOCATION:School field\r\n" in ics
    # Times are sent in UTC; Kuala Lumpur is UTC+8.
    assert "DTSTART:20261103T000000Z\r\n" in ics
    assert "DTEND:20261103T043000Z\r\n" in ics
    assert f"URL:https://school.example/events/{event.pk}/\r\n" in ics
    assert f"UID:event-{event.pk}@school.example\r\n" in ics


@pytest.mark.django_db
def test_all_day_event_covers_whole_days(client):
    event = Event.objects.create(
        title="School holiday",
        all_day=True,
        starts_at=datetime(2026, 12, 21, 9, 0, tzinfo=KL),
        ends_at=datetime(2026, 12, 23, 9, 0, tzinfo=KL),
    )

    ics = get_ics(client, reverse("portal:event_calendar", args=[event.pk]))

    # The end date is the day after the last day, as the calendar format expects.
    assert "DTSTART;VALUE=DATE:20261221\r\n" in ics
    assert "DTEND;VALUE=DATE:20261224\r\n" in ics


@pytest.mark.django_db
def test_event_without_end_lasts_one_hour(client):
    event = Event.objects.create(
        title="Assembly", starts_at=datetime(2026, 11, 3, 7, 30, tzinfo=KL)
    )

    ics = get_ics(client, reverse("portal:event_calendar", args=[event.pk]))

    assert "DTSTART:20261102T233000Z\r\n" in ics
    assert "DTEND:20261103T003000Z\r\n" in ics


def test_commas_and_new_lines_are_kept_safe(make_event, client):
    event = make_event("Sports, games; and fun", description="Bring water\nWear shoes")

    ics = unfold(get_ics(client, reverse("portal:event_calendar", args=[event.pk])))

    assert "SUMMARY:Sports\\, games\\; and fun\r\n" in ics
    assert "Bring water\\nWear shoes" in ics


def test_long_tamil_lines_are_folded_without_breaking_letters(make_event, client):
    text = "பெற்றோர் ஆசிரியர் சங்கக் கூட்டம் " * 10
    event = make_event(title_ta=text, description_ta=text)

    ics = get_ics(client, reverse("portal:event_calendar", args=[event.pk]))

    for line in ics.split("\r\n"):
        assert len(line.encode()) <= 75
    assert text.strip() in unfold(ics)


def test_draft_event_has_no_calendar_file(make_event, client):
    event = make_event("Draft trip", is_published=False)
    response = client.get(reverse("portal:event_calendar", args=[event.pk]))
    assert response.status_code == 404


def test_feed_lists_published_events_from_last_three_months_on(make_event, client):
    make_event("Coming soon", days=10)
    make_event("Last month", days=-30)
    make_event("Last year", days=-200)
    make_event("Draft trip", days=5, is_published=False)

    ics = get_ics(client, reverse("portal:calendar_feed"))

    assert "SUMMARY:Coming soon" in ics
    assert "SUMMARY:Last month" in ics
    assert "Last year" not in ics
    assert "Draft trip" not in ics
    assert "X-WR-CALNAME:" in ics


def test_feed_is_in_tamil_even_for_english_visitors(make_event, client):
    make_event(title_ta="விளையாட்டு நாள்", title_en="Sports day")

    ics = get_ics(client, reverse("portal:calendar_feed"))

    assert "SUMMARY:விளையாட்டு நாள்" in ics
    assert "Sports day" not in ics


def test_event_page_has_add_to_calendar_button(make_event, client):
    event = make_event("Sports day")

    html = client.get(event.get_absolute_url()).content.decode()

    assert "Add to my calendar" in html
    assert reverse("portal:event_calendar", args=[event.pk]) in html


@pytest.mark.django_db
def test_events_page_offers_calendar_subscription(client, settings):
    settings.SITE_URL = "https://school.example"

    html = client.get(reverse("portal:event_list")).content.decode()

    assert "Get every school event on your phone" in html
    assert 'href="webcal://school.example/events/calendar.ics"' in html
    assert (
        "https://calendar.google.com/calendar/r?cid="
        "webcal%3A%2F%2Fschool.example%2Fevents%2Fcalendar.ics" in html
    )


def test_feed_includes_event_happening_now(make_event, client):
    """An event that started an hour ago is still in the feed."""
    event = make_event("Running now", days=0)
    Event.objects.filter(pk=event.pk).update(starts_at=timezone.now() - timedelta(hours=1))

    assert "SUMMARY:Running now" in get_ics(client, reverse("portal:calendar_feed"))
