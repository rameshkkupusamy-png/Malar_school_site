from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from portal.models import Event


def test_home_shows_next_upcoming_published_event(client, make_event):
    make_event("Science fair", days=3)
    make_event("Sports day", days=10)
    make_event("Hidden draft", days=1, is_published=False)
    make_event("Last term's concert", days=-30)

    response = client.get(reverse("portal:home"))

    assert response.context["next_event"].title == "Science fair"
    assert [e.title for e in response.context["later_events"]] == ["Sports day"]
    assert b"Hidden draft" not in response.content
    assert b"concert" not in response.content


def test_home_without_events_shows_empty_state(client, db):
    response = client.get(reverse("portal:home"))
    assert b"Nothing on the calendar yet" in response.content


def test_event_in_progress_counts_as_upcoming(client, make_event):
    make_event("Book week", days=-1, ends_at=timezone.now() + timedelta(days=2))
    response = client.get(reverse("portal:home"))
    assert response.context["next_event"].title == "Book week"
    assert b"Happening now" in response.content


def test_event_list_past_tab(client, make_event):
    make_event("Upcoming trip", days=5)
    make_event("Old trip", days=-5)

    upcoming = client.get(reverse("portal:event_list"))
    past = client.get(reverse("portal:event_list") + "?show=past")

    assert [e.title for e in upcoming.context["page"]] == ["Upcoming trip"]
    assert [e.title for e in past.context["page"]] == ["Old trip"]


def test_unpublished_event_detail_is_404(client, make_event):
    event = make_event(is_published=False)
    assert client.get(event.get_absolute_url()).status_code == 404


def test_published_event_detail(client, make_event):
    event = make_event("Parents evening", location="Main hall")
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    assert b"Main hall" in response.content


@pytest.mark.django_db
def test_event_end_before_start_is_invalid():
    now = timezone.now()
    event = Event(title="Bad", starts_at=now, ends_at=now - timedelta(hours=1))
    with pytest.raises(ValidationError):
        event.full_clean()
