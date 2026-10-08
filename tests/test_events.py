from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from portal.models import Announcement, Event


def test_home_leads_with_next_event_when_there_is_no_news(client, make_event):
    make_event("Science fair", days=3)
    make_event("Sports day", days=10)
    make_event("Hidden draft", days=1, is_published=False)
    make_event("Last term's concert", days=-30)

    response = client.get(reverse("portal:home"))

    assert response.context["lead_news"] is None
    assert response.context["hero_event"].title == "Science fair"
    assert [e.title for e in response.context["coming_up"]] == ["Sports day"]
    assert b"Hidden draft" not in response.content
    assert b"concert" not in response.content


def test_home_leads_with_news_and_lists_all_upcoming_events(client, make_event):
    now = timezone.now()
    Announcement.objects.create(title="Latest", body="x", published_at=now - timedelta(hours=1))
    Announcement.objects.create(
        title="Office closed Friday", body="x", is_pinned=True, published_at=now - timedelta(days=3)
    )
    Announcement.objects.create(title="Scheduled", body="x", published_at=now + timedelta(days=1))
    make_event("Science fair", days=3)
    make_event("Sports day", days=10)

    response = client.get(reverse("portal:home"))

    assert response.context["lead_news"].title == "Office closed Friday"  # pinned beats newer
    assert [a.title for a in response.context["more_news"]] == ["Latest"]
    assert response.context["hero_event"] is None
    assert [e.title for e in response.context["coming_up"]] == ["Science fair", "Sports day"]
    page = response.content.decode()
    assert page.index("Office closed Friday") < page.index("Science fair")
    assert "Scheduled" not in page


def test_home_without_events_shows_empty_state(client, db):
    response = client.get(reverse("portal:home"))
    assert b"Welcome to SJK (T) Ladang Semenyih" in response.content
    assert b"Nothing is planned yet" in response.content
    assert response.context["hero_image"] is None


def test_event_in_progress_counts_as_upcoming(client, make_event):
    make_event("Book week", days=-1, ends_at=timezone.now() + timedelta(days=2))
    response = client.get(reverse("portal:home"))
    assert response.context["hero_event"].title == "Book week"
    assert b"Happening now" in response.content


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
